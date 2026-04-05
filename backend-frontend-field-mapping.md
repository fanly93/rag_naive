# 前后端接口对齐要点与字段映射（实施版）

本文件用于完成 todo 中的“`frontend-api-contract.md` 对齐要点与字段映射”，  
目标是让后端实现时可以按表直接对照，不遗漏关键字段和语义。

---

## 1. 对齐基线

- 前端契约来源：`frontend-api-contract.md`
- 后端需求来源：`backend-requirements.md`
- 对齐原则：**字段名一致 > 语义一致 > 类型一致 > 错误码一致**

---

## 2. 核心接口映射矩阵

## 2.1 会话管理

| 前端接口 | 后端实现建议 | 关键字段 | 备注 |
|---|---|---|---|
| `GET /sessions` | `GET /api/v1/sessions` | `id,title,updated_at,is_draft,knowledge_base_id` | `updated_at` 必须可排序 |
| `POST /sessions` | `POST /api/v1/sessions` | `title,is_draft` | 新建空会话 `is_draft=true` |
| `DELETE /sessions/{session_id}` | `DELETE /api/v1/sessions/{session_id}` | `session_id` | 删除后需联动清理绑定关系 |

## 2.2 知识库管理

| 前端接口 | 后端实现建议 | 关键字段 | 备注 |
|---|---|---|---|
| `POST /knowledge-bases` | `POST /api/v1/knowledge-bases` | `session_id,name,chunk_size,chunk_overlap,file` | `multipart/form-data` |
| `POST /knowledge-bases/{id}/files` | `POST /api/v1/knowledge-bases/{id}/files` | `file` | 返回新的 `task_id` |
| `DELETE /knowledge-bases/{id}` | `DELETE /api/v1/knowledge-bases/{id}` | `knowledge_base_id` | 删除后前端右栏回空态 |
| `DELETE /knowledge-bases/{id}/files/{file_id}` | `DELETE /api/v1/knowledge-bases/{id}/files/{file_id}` | `remaining_file_count` | 为 0 时前端会回空态 |
| `GET /sessions/{session_id}/knowledge-base` | `GET /api/v1/sessions/{session_id}/knowledge-base` | `KnowledgeBase \\| null` | 会话切换时右栏同步依赖此接口 |

## 2.3 构建任务

| 前端接口 | 后端实现建议 | 关键字段 | 备注 |
|---|---|---|---|
| `GET /build-tasks/{task_id}` | `GET /api/v1/build-tasks/{task_id}` | `stage,progress,error_message` | `stage` 需与前端状态机对齐 |

`stage` 枚举要求：

- `uploaded`
- `chunking`
- `indexing`
- `vectorizing`
- `done`
- `failed`

## 2.4 召回测试（右侧）

| 前端接口 | 后端实现建议 | 关键字段 | 备注 |
|---|---|---|---|
| `POST /knowledge-bases/{id}/retrieve-test` | `POST /api/v1/knowledge-bases/{id}/retrieve-test` | `query,mode,top_n,top_k` | 返回 `initial_results` + `final_results` |

`mode` 枚举要求：

- `vector`
- `hybrid`
- `hybrid_rerank`

响应字段要求：

- `initial_results`: Top-N 初召回（供折叠下拉）
- `final_results`: Top-K 最终结果（默认展示）

## 2.5 聊天问答（中间）

| 前端接口 | 后端实现建议 | 关键字段 | 备注 |
|---|---|---|---|
| `POST /chat/completions` | `POST /api/v1/chat/completions` | `session_id,query,mode,top_n,top_k` | `mode=none` 时不走知识库 |

响应字段要求：

- `assistant_message.content`：正文中应有引用标记 `[1][2][3]`
- `citations_top_k`：用于中间区域“Top-K 单独框”
- `citations_top_n`：用于中间区域“Top-N 折叠下拉”

## 2.6 片段详情

| 前端接口 | 后端实现建议 | 关键字段 | 备注 |
|---|---|---|---|
| `GET /chunks/{chunk_id}` | `GET /api/v1/chunks/{chunk_id}` | `source,score,channel,hit_mode,content` | 中间/右侧弹窗共用 |

---

## 3. 字段级映射（重点）

## 3.1 检索片段字段（必须统一）

| 前端字段 | 后端字段 | 类型 | 说明 |
|---|---|---|---|
| `chunk_id` | `chunk_id` | string | 片段唯一 ID |
| `title` | `title` | string | 片段标题 |
| `source` | `source` | string | 来源文档 |
| `score` | `score` | number | 相关性分值 |
| `content` | `content` | string | 全文内容 |
| `channel` | `channel` | string | `vector/bm25/rerank` |
| `hit_mode` | `hit_mode` | string | 前端展示文案 |

## 3.2 引用字段（聊天）

| 前端字段 | 后端字段 | 类型 | 说明 |
|---|---|---|---|
| `citations_top_k[].index` | `index` | integer | 从 1 开始 |
| `citations_top_k[].chunk_id` | `chunk_id` | string | 对应详情接口 ID |
| `citations_top_k[].preview` | `preview` | string | 前 30 字 |
| `citations_top_n[].index` | `index` | integer | Top-N 序号 |
| `citations_top_n[].chunk_id` | `chunk_id` | string | 对应详情接口 ID |
| `citations_top_n[].preview` | `preview` | string | 前 30 字 |

---

## 4. 参数校验对齐

后端需要与前端完全一致：

- `name`: 2-50 字符
- `chunk_size`: 256-4096
- `chunk_overlap`: 0-512 且 `< chunk_size`
- `top_n >= 1`
- `top_k >= 1`
- `top_k <= top_n`

---

## 5. 错误码对齐

| 码值 | 场景 | 前端行为 |
|---|---|---|
| `1001` | 参数错误 | 直接提示 `message` |
| `1002` | 资源不存在 | 回空态并提示 |
| `1003` | 状态冲突 | 保持当前状态并提示 |
| `2001` | 文件格式不支持 | 上传失败提示 |
| `3001` | 检索失败 | 召回区提示失败 |
| `3002` | 重排/模型失败 | 问答区可重试 |

---

## 6. 联调检查清单

- [ ] 会话切换时，右侧知识库与召回状态按 `session_id` 隔离
- [ ] 聊天回复中有 `[1][2][3]`，且 `citations_top_k` 可展开点击详情
- [ ] 中间区 Top-N 为折叠下拉，数据来自 `citations_top_n`
- [ ] 右侧默认展示 Top-K，且可展开 Top-N 初召回
- [ ] `GET /chunks/{chunk_id}` 可服务中间与右侧两种弹窗
- [ ] 所有接口统一返回 `{code,message,data}`

---

## 7. 建议实现顺序（对齐优先）

1. 实现 `retrieve-test` + `chunks/{chunk_id}`（先跑通右侧）
2. 实现 `chat/completions` 返回 `citations_top_k/top_n`
3. 实现 `sessions/{id}/knowledge-base` 与状态隔离
4. 最后打通上传构建全链路并接任务进度
