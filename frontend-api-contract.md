# Agentic RAG 前后端接口字段说明（V1）

本文档用于对齐当前前端已完成功能与后端接口设计，便于后续联调。  
范围覆盖：会话管理、知识库管理、构建任务、召回测试、聊天问答、片段详情。

---

## 1. 全局约定

### 1.1 基础信息

- Base URL（示例）：`/api/v1`
- 内容类型：`application/json`
- 时间字段：ISO8601，例如 `2026-04-04T11:00:00+08:00`
- 分页默认：`page=1`、`page_size=20`

### 1.2 通用响应结构

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

- `code=0` 表示成功，非 0 表示失败
- 前端建议依赖 `code` 与 `message` 展示错误提示

### 1.3 通用错误码建议

- `1001` 参数校验失败
- `1002` 资源不存在（会话/知识库/文件）
- `1003` 状态冲突（如构建中不允许重复触发）
- `2001` 文件格式不支持
- `3001` 检索失败
- `3002` 模型推理失败

---

## 2. 数据模型（字段定义）

## 2.1 Session（会话）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string | 是 | 会话 ID |
| title | string | 是 | 会话标题 |
| updated_at | string | 是 | 最近更新时间 |
| is_draft | boolean | 是 | 是否空白会话 |
| knowledge_base_id | string/null | 否 | 该会话绑定的知识库 ID |

## 2.2 KnowledgeBase（知识库）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string | 是 | 知识库 ID |
| name | string | 是 | 知识库名称 |
| chunk_size | integer | 是 | 切分长度（256-4096） |
| chunk_overlap | integer | 是 | 切分重叠（0-512，且 `< chunk_size`） |
| status | string | 是 | `empty/building/ready/failed` |
| files | array\<KBFile\> | 是 | 已上传文件列表 |
| created_at | string | 是 | 创建时间 |
| updated_at | string | 是 | 更新时间 |

## 2.3 KBFile（知识库文件）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string | 是 | 文件 ID |
| filename | string | 是 | 文件名 |
| size | integer | 否 | 字节数 |
| mime_type | string | 否 | MIME 类型 |
| status | string | 是 | `uploaded/indexing/ready/failed` |
| uploaded_at | string | 是 | 上传时间 |

## 2.4 BuildTask（构建任务）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | 是 | 任务 ID |
| knowledge_base_id | string | 是 | 知识库 ID |
| stage | string | 是 | `uploaded/chunking/indexing/vectorizing/done/failed` |
| progress | integer | 是 | 0-100 |
| error_message | string/null | 否 | 失败信息 |

## 2.5 RetrievalChunk（召回片段）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| chunk_id | string | 是 | 片段 ID |
| title | string | 是 | 片段标题 |
| source | string | 是 | 来源文档名 |
| score | number | 是 | 相似度或重排分 |
| content | string | 是 | 片段全文 |
| channel | string | 是 | `vector/bm25/rerank` |
| hit_mode | string | 是 | 展示用命中方式文案 |

## 2.6 Message（聊天消息）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string | 是 | 消息 ID |
| role | string | 是 | `user/assistant` |
| content | string | 是 | 消息文本 |
| citations | array\<Citation\> | 否 | 助手消息引用 |
| created_at | string | 是 | 创建时间 |

## 2.7 Citation（引用）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| index | integer | 是 | 引用序号，1 开始 |
| chunk_id | string | 是 | 对应片段 ID |
| preview | string | 是 | 前端展示前 30 字 |

---

## 3. 接口清单

## 3.1 会话管理

### 3.1.1 查询会话列表

- `GET /sessions`

响应 `data`:

```json
{
  "items": [
    {
      "id": "sess_001",
      "title": "Agentic RAG 方案讨论",
      "updated_at": "2026-04-04T11:00:00+08:00",
      "is_draft": false,
      "knowledge_base_id": "kb_001"
    }
  ]
}
```

### 3.1.2 新建会话

- `POST /sessions`

请求 `data`:

```json
{
  "title": "新会话",
  "is_draft": true
}
```

响应：`Session`

### 3.1.3 删除会话

- `DELETE /sessions/{session_id}`

响应：

```json
{
  "code": 0,
  "message": "deleted",
  "data": {
    "session_id": "sess_001"
  }
}
```

---

## 3.2 知识库管理

### 3.2.1 创建知识库（含首个文件）

- `POST /knowledge-bases`
- `multipart/form-data`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| session_id | string | 是 | 当前会话 ID |
| name | string | 是 | 知识库名称（2-50） |
| chunk_size | integer | 是 | 256-4096 |
| chunk_overlap | integer | 是 | 0-512 且 `< chunk_size` |
| file | file | 是 | `.txt/.md/.pdf` |

响应：

```json
{
  "code": 0,
  "message": "accepted",
  "data": {
    "knowledge_base_id": "kb_001",
    "task_id": "task_001",
    "status": "building"
  }
}
```

### 3.2.2 给知识库追加文件

- `POST /knowledge-bases/{knowledge_base_id}/files`
- `multipart/form-data`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | file | 是 | 新上传文件 |

响应：返回新的 `task_id`

### 3.2.3 删除知识库

- `DELETE /knowledge-bases/{knowledge_base_id}`

响应：`deleted`

### 3.2.4 删除知识库文件

- `DELETE /knowledge-bases/{knowledge_base_id}/files/{file_id}`

响应：

```json
{
  "code": 0,
  "message": "deleted",
  "data": {
    "knowledge_base_id": "kb_001",
    "file_id": "file_001",
    "remaining_file_count": 1
  }
}
```

### 3.2.5 查询会话绑定知识库

- `GET /sessions/{session_id}/knowledge-base`

响应：`KnowledgeBase | null`

---

## 3.3 构建任务

### 3.3.1 查询构建进度

- `GET /build-tasks/{task_id}`

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "task_001",
    "knowledge_base_id": "kb_001",
    "stage": "indexing",
    "progress": 60,
    "error_message": null
  }
}
```

> 前端当前支持“最小化构建弹层”，建议后端轮询频率 1s-2s。

---

## 3.4 召回测试（右侧）

### 3.4.1 执行召回测试

- `POST /knowledge-bases/{knowledge_base_id}/retrieve-test`

请求：

```json
{
  "query": "谷歌",
  "mode": "hybrid_rerank",
  "top_n": 20,
  "top_k": 3
}
```

`mode` 可选：

- `vector`
- `hybrid`
- `hybrid_rerank`

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "query": "谷歌",
    "initial_results": [
      {
        "chunk_id": "ch_001",
        "title": "文档片段1 · Agentic RAG 入门指南",
        "source": "Agentic-RAG-Guide.md",
        "score": 0.92,
        "content": "......",
        "channel": "vector",
        "hit_mode": "vector"
      }
    ],
    "final_results": [
      {
        "chunk_id": "ch_009",
        "title": "文档片段2 · LlamaIndex 检索实践",
        "source": "LlamaIndex-Retrieval.md",
        "score": 0.95,
        "content": "......",
        "channel": "rerank",
        "hit_mode": "Rerank（来自 vector）"
      }
    ]
  }
}
```

---

## 3.5 聊天问答（中间）

### 3.5.1 发送消息（含可选知识库检索）

- `POST /chat/completions`

请求：

```json
{
  "session_id": "sess_001",
  "query": "请解释 Agentic RAG",
  "mode": "hybrid_rerank",
  "top_n": 20,
  "top_k": 3
}
```

说明：

- 当 `mode=none` 时，表示不使用知识库检索
- 非 `none` 时，后端返回引用片段用于前端展示 `[1][2][3]`

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "assistant_message": {
      "id": "msg_a_001",
      "role": "assistant",
      "content": "...... 引用标记：[1][2][3]",
      "citations_top_k": [
        { "index": 1, "chunk_id": "ch_101", "preview": "前30字符......" },
        { "index": 2, "chunk_id": "ch_102", "preview": "前30字符......" },
        { "index": 3, "chunk_id": "ch_103", "preview": "前30字符......" }
      ],
      "citations_top_n": [
        { "index": 1, "chunk_id": "ch_001", "preview": "前30字符......" }
      ],
      "created_at": "2026-04-04T12:00:00+08:00"
    }
  }
}
```

---

## 3.6 片段详情

### 3.6.1 获取片段详情（弹窗）

- `GET /chunks/{chunk_id}`

响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "chunk_id": "ch_101",
    "title": "文档片段2 · LlamaIndex 检索实践",
    "source": "LlamaIndex-Retrieval.md",
    "score": 0.95,
    "channel": "rerank",
    "hit_mode": "Rerank（来自 vector）",
    "content": "完整片段全文......"
  }
}
```

---

## 4. 前端与后端对齐重点

### 4.1 已实现前端校验（后端也需兜底）

- `knowledge_base_name`: 2-50
- `chunk_size`: 256-4096
- `chunk_overlap`: 0-512 且 `< chunk_size`
- `top_n >= 1`、`top_k >= 1`、`top_k <= top_n`

### 4.2 当前前端交互要求

- 中间问答区：
  - Top-K 引用来源为“独立列表框”，展示前 30 字，点击弹窗
  - Top-N 初召回为折叠下拉，默认收起，展开可点详情
- 右侧召回区：
  - 默认展示 Top-K 最终结果
  - Top-N 初召回为折叠下拉
- 会话切换时，知识库与召回状态需按 `session_id` 隔离

---

## 5. 联调顺序建议

1. 先打通 `会话列表 + 创建 + 删除`
2. 再打通 `创建知识库 + 构建进度查询`
3. 接 `召回测试`（先 mock 内容，再接真实检索）
4. 接 `聊天问答` + 引用字段
5. 最后补 `片段详情接口`

---

## 6. 版本建议

- 当前文档版本：`v1`
- 建议后续新增 `v1.1`：
  - 支持 SSE/流式回答
  - 支持引用索引与正文 token 对齐（点击 `[1]` 直接定位）
  - 支持知识库多租户隔离字段（如 `workspace_id`）
