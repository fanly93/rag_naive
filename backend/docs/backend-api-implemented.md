# 后端接口实现说明（已实现清单）

本文档基于当前代码实现整理，描述已落地的后端 API、字段约束、错误码与联调注意事项。

## 1. 基础信息

- 服务框架：`FastAPI`
- API 前缀：`/api/v1`
- 服务根路由：`GET /`（不带前缀）
- 当前已注册路由模块：
  - `health`
  - `sessions`
  - `knowledge-bases`
  - `build-tasks`
  - `chunks`
  - `chat`

## 2. 统一响应结构

除流式接口外，统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

- `code=0`：成功
- 非 `0`：业务错误（详见“错误码”章节）

## 3. 错误处理与错误码

### 3.1 全局异常包装

- `HTTPException`：若已包含 `code/message/data`，原样返回
- `KeyError`：返回 `404` + `code=1002`
- 其他异常：返回 `500` + `code=5000`

### 3.2 已使用错误码

- `1001` 参数校验失败（如 `top_k > top_n`、chunk 参数非法、缺少知识库）
- `1002` 资源不存在（session/kb/task/chunk 不存在）
- `1003` 状态冲突（构建任务非 failed 状态重试）
- `2001` 文件类型不支持/缺扩展名
- `3001` 检索失败
- `4001` 模型问答调用失败
- `5000` 未捕获内部异常

## 4. 接口总览

### 4.1 健康检查

#### `GET /api/v1/health`

- 功能：服务健康检查
- 响应 `data`：
  - `status`: `"ok"`

### 4.2 会话管理（sessions）

#### `GET /api/v1/sessions`

- 功能：获取会话列表（按更新时间倒序）
- 响应 `data.items[]` 字段：
  - `id: string`
  - `title: string`
  - `updated_at: datetime`
  - `is_draft: bool`
  - `knowledge_base_id: string | null`

#### `POST /api/v1/sessions`

- 功能：创建会话
- 请求体：
  - `title: string`（1~100）
  - `is_draft: bool`（默认 `true`）
- 成功状态码：`201`
- 响应 `data`：同会话对象

#### `DELETE /api/v1/sessions/{session_id}`

- 功能：删除会话
- 成功响应 `data`：
  - `session_id: string`
- 失败：
  - `404` + `1002`（session 不存在）

#### `GET /api/v1/sessions/{session_id}/knowledge-base`

- 功能：查询会话绑定的知识库
- 响应 `data`：
  - `KnowledgeBase` 对象，或 `null`
- 失败：
  - `404` + `1002`（session 不存在）

#### `GET /api/v1/sessions/{session_id}/messages`

- 功能：获取指定会话的消息历史（按时间升序，user 优先于同时间 assistant）
- 响应 `data.items[]` 字段：
  - `id: string`
  - `session_id: string`
  - `role: "user"|"assistant"`
  - `content: string`
  - `is_error: bool`
  - `created_at: datetime`
  - `top_n_citations: RetrievalChunk[]`（仅 assistant 消息可能有值）
  - `top_k_citations: RetrievalChunk[]`（仅 assistant 消息可能有值）
- 失败：
  - `404 + 1002`（session 不存在）

### 4.3 知识库管理（knowledge-bases）

#### `POST /api/v1/knowledge-bases`

- 功能：创建知识库并触发异步构建任务
- 请求类型：`multipart/form-data`
- 表单字段：
  - `session_id: string`
  - `name: string`（2~50）
  - `chunk_size: int`（256~4096）
  - `chunk_overlap: int`（0~512 且 `< chunk_size`）
  - `file: UploadFile`（仅支持 `.txt/.md/.pdf`）
- 成功状态码：`201`
- 响应 `data`：
  - `knowledge_base_id: string`
  - `task_id: string`
  - `status: "building"`
- 常见失败：
  - `404 + 1002`：session 不存在
  - `400 + 1001`：参数非法
  - `400 + 2001`：文件扩展名问题/格式不支持

#### `POST /api/v1/knowledge-bases/{knowledge_base_id}/files`

- 功能：向知识库追加文件并触发异步构建任务
- 请求类型：`multipart/form-data`
- 表单字段：
  - `file: UploadFile`（`.txt/.md/.pdf`）
- 响应 `data`：
  - `knowledge_base_id: string`
  - `task_id: string`
  - `status: "building"`
- 失败：
  - `404 + 1002`：知识库不存在
  - `400 + 2001`：文件不合法

#### `DELETE /api/v1/knowledge-bases/{knowledge_base_id}`

- 功能：删除知识库，并自动解绑关联会话
- 响应 `data`：
  - `knowledge_base_id: string`
- 失败：
  - `404 + 1002`

#### `DELETE /api/v1/knowledge-bases/{knowledge_base_id}/files/{file_id}`

- 功能：删除知识库内单个文件
- 响应 `data`：
  - `knowledge_base_id: string`
  - `file_id: string`
  - `remaining_file_count: int`
- 失败：
  - `404 + 1002`（知识库或文件不存在）

#### `GET /api/v1/knowledge-bases/{knowledge_base_id}`

- 功能：获取知识库详情
- 响应 `data` 字段：
  - `id: string`
  - `name: string`
  - `chunk_size: int`
  - `chunk_overlap: int`
  - `status: "empty"|"building"|"ready"|"failed"`
  - `files[]`（`id/filename/size/mime_type/status/uploaded_at`）
  - `created_at: datetime`
  - `updated_at: datetime`
- 失败：
  - `404 + 1002`

#### `POST /api/v1/knowledge-bases/{knowledge_base_id}/retrieve-test`

- 功能：召回测试（两阶段）
- 请求体：
  - `query: string`
  - `mode: "vector"|"hybrid"|"hybrid_rerank"`
  - `top_n: int >= 1`
  - `top_k: int >= 1`
- 约束：
  - `top_k <= top_n`
- 响应 `data`：
  - `query: string`
  - `initial_results: RetrievalChunk[]`（初召回）
  - `final_results: RetrievalChunk[]`（最终结果）
- `RetrievalChunk` 字段：
  - `chunk_id`
  - `title`
  - `source`
  - `score`
  - `content`
  - `channel: "vector"|"bm25"|"rerank"`
  - `hit_mode: string`
- 失败：
  - `404 + 1002`：知识库不存在
  - `400 + 1001`：`top_k > top_n`
  - `500 + 3001`：检索异常

### 4.4 构建任务（build-tasks）

#### `GET /api/v1/build-tasks/{task_id}`

- 功能：查询构建任务状态
- 响应 `data`：
  - `task_id: string`
  - `knowledge_base_id: string`
  - `stage: "uploaded"|"chunking"|"indexing"|"vectorizing"|"done"|"failed"`
  - `progress: int (0~100)`
  - `error_message: string | null`
  - `updated_at: datetime`
- 失败：
  - `404 + 1002`

#### `POST /api/v1/build-tasks/{task_id}/retry`

- 功能：重试失败任务
- 响应 `data`：
  - `task_id: string`
  - `stage: BuildStage`
  - `progress: int`
- 失败：
  - `404 + 1002`：任务不存在
  - `409 + 1003`：任务当前不在 `failed` 状态

### 4.5 片段详情（chunks）

#### `GET /api/v1/chunks/{chunk_id}`

- 功能：按全局 `chunk_id` 查询片段详情
- 响应 `data`：`RetrievalChunk`
- 失败：
  - `404 + 1002`

#### `GET /api/v1/knowledge-bases/{knowledge_base_id}/chunks/{chunk_id}`

- 功能：按知识库上下文查询片段详情
- 响应 `data`：`RetrievalChunk`
- 失败：
  - `404 + 1002`（chunk 不在该知识库或不存在）

### 4.6 聊天问答（chat）

#### `POST /api/v1/chat/completions`

- 功能：非流式问答（支持可选 RAG 检索）
- 请求体：
  - `session_id: string`
  - `query: string`
  - `mode: "none"|"vector"|"hybrid"|"hybrid_rerank"`（默认 `hybrid_rerank`）
  - `top_n: int >= 1`（默认 `20`）
  - `top_k: int >= 1`（默认 `3`）
  - `knowledge_base_id?: string | null`
  - `provider?: "deepseek"|"openai"|"dashscope"`
  - `model?: string`
- 行为说明：
  - `mode="none"`：不检索知识库，直接模型回答
  - `mode!=none`：需要可用知识库（来自请求或会话绑定）
  - 自动多轮记忆：服务端会在当前问题前，拼接该 `session_id` 下最近若干轮历史消息
  - 历史过滤规则：
    - 仅保留 `role in {"user","assistant"}` 的消息
    - 自动过滤 `is_error=true` 的异常回复
    - 单条消息会做长度截断（默认 `HISTORY_MAX_CHARS=1200`）
    - 仅保留最近 `HISTORY_TURNS_LIMIT` 轮（默认 `8` 轮，即最多 `16` 条 user/assistant 消息）
  - 会话隔离：历史消息严格按 `session_id` 读取，不会跨会话串话
- 响应 `data`：
  - `answer: string`
  - `provider: "deepseek"|"openai"|"dashscope"`
  - `model: string`
  - `mode`
  - `top_n`
  - `top_k`
  - `initial_results: RetrievalChunk[]`
  - `final_results: RetrievalChunk[]`
- 失败：
  - `404 + 1002`：session 或知识库不存在
  - `400 + 1001`：参数校验失败/缺知识库
  - `500 + 3001`：检索失败
  - `500 + 4001`：模型调用失败

#### `POST /api/v1/chat/completions/stream`

- 功能：流式问答（SSE）
- 请求体：同非流式接口
- 响应类型：`text/event-stream`
- 事件流格式：
  - `event: meta`
    - `provider/model/mode/top_n/top_k`
    - `initial_results/final_results`
  - `event: delta`
    - `content`（增量 token）
  - `event: done`
    - `answer`（聚合后的完整文本）
  - `event: error`
    - `message`（流过程中异常）
- 失败（请求阶段）：
  - 同非流式接口（`1001/1002/3001/4001`）
  - 历史记忆行为与非流式接口一致（同样自动拼接最近历史并做过滤/截断）

## 5. 根路由与服务探活

### `GET /`

- 响应 `data`：
  - `service: string`
  - `status: "running"`

## 6. 联调注意事项

- 文件上传接口必须使用 `multipart/form-data`
- 召回类接口必须保证 `top_k <= top_n`
- `mode!=none` 且会话无绑定知识库时，需显式传 `knowledge_base_id`
- 流式接口前端需按 SSE 协议解析 `meta/delta/done/error`
- 片段详情弹窗建议优先使用知识库上下文接口：
  - `/api/v1/knowledge-bases/{knowledge_base_id}/chunks/{chunk_id}`

## 7. 已实现状态结论

当前文档列出的接口均已在代码中实现并注册，已用于前后端联调与 Phase6 回归。
