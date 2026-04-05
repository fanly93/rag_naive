# Agentic RAG 后端总体需求文档（V1）

本文档用于后端开发统一对齐，整合以下内容：

- LlamaIndex：RAG 主体（读取、切分、向量化、入库、检索）
- LangChain/LangGraph：Agent 工具编排
- 前后端接口对齐：基于现有 `frontend-api-contract.md`

---

## 1. 目标与范围

## 1.1 目标

构建一个可对接当前前端的 Agentic RAG 后端，满足：

1. 文档上传后可完成索引构建并写入 Milvus  
2. 支持召回测试（Top-K 默认展示 + Top-N 折叠查看）  
3. 聊天问答支持 `[1][2][3]` 引用标记与可追溯来源  
4. 支持多模型切换（DeepSeek/OpenAI/DashScope）

## 1.2 范围（V1）

- FastAPI API 层
- LlamaIndex RAG 服务层
- LangChain Agent 工具化层
- 构建任务状态管理（轮询）
- 与前端字段、状态流转对齐

## 1.3 非目标（V1 暂不做）

- 多租户权限体系
- 流式增量 token 推送（可在 V1.1 增加 SSE）
- 复杂工作流编排平台化

---

## 2. 技术选型与版本基线

- Web 框架：FastAPI
- Python 环境：`venv`（必须在虚拟环境中开发）
- RAG 框架：LlamaIndex（core + integrations）
- Agent 框架：LangChain + LangGraph
- 向量数据库：Milvus（本地 Docker）

模型策略：

- 默认 Chat：`deepseek-chat`
- Embedding：DashScope `text-embedding-v4`
- Rerank：DashScope `qwen3-rerank`
- 可切换 Chat Provider：DeepSeek / OpenAI / DashScope

---

## 3. 系统架构

## 3.1 分层结构

- `api/`：HTTP 接口、参数校验、响应封装
- `service/`：业务编排（会话、知识库、任务）
- `rag/`：LlamaIndex 能力（ingest/retrieve/rerank）
- `agent/`：LangChain Tool + LangGraph 流程
- `repository/`：Milvus 与元数据存取
- `config/`：环境变量与模型路由
- `schemas/`：Pydantic 数据模型

## 3.2 核心数据流

1. 上传文件 -> 创建/追加知识库 -> 启动构建任务  
2. 构建任务分阶段执行：`uploaded -> chunking -> indexing -> vectorizing -> done/failed`  
3. 召回测试：按 `mode/top_n/top_k` 返回 `initial_results` 与 `final_results`  
4. 聊天问答：Agent 判断是否调用 RAG Tool，返回正文 + 引用

---

## 4. 模块详细需求

## 4.1 文档构建模块（LlamaIndex）

输入：

- 知识库名称
- `chunk_size`
- `chunk_overlap`
- 文件（`.txt/.md/.pdf`）

流程：

1. `SimpleDirectoryReader` 或指定 reader 读取文档  
2. `SentenceSplitter` 切分节点（保留 metadata）  
3. embedding（DashScope）  
4. 写入 Milvus（collection 维度与 embedding 维度一致）

输出：

- `knowledge_base_id`
- `task_id`
- 状态可轮询

## 4.2 检索模块（RAG Query）

输入：

- `query`
- `mode`: `vector | hybrid | hybrid_rerank | none`
- `top_n`
- `top_k`
- `session_id / knowledge_base_id`

输出：

- `initial_results`（Top-N，供折叠下拉）
- `final_results`（Top-K，供默认展示和引用）

约束：

- `top_k <= top_n`
- `mode=none` 时不执行检索

## 4.3 Agent 模块（LangChain/LangGraph）

能力：

- 将 RAG 检索封装为 Tool（如 `query_knowledge_base`）
- Agent 可决定直接回答或调用 Tool
- 返回统一结构：`assistant_text + citations_top_k + citations_top_n`

输出要求（前端强相关）：

- 正文包含引用标记 `[1][2][3]`
- Top-K 来源列表（前 30 字预览）
- Top-N 初召回列表（前 30 字预览）
- 点击后可用 `chunk_id` 拉详情

---

## 5. API 对齐要求

与 `frontend-api-contract.md` 保持一致，后端必须覆盖以下接口族：

- 会话管理：列表、创建、删除
- 知识库管理：创建、追加文件、删文件、删库、按会话查询绑定
- 构建任务：任务进度查询
- 召回测试：返回 Top-N + Top-K
- 聊天问答：返回正文 + 引用结构
- 片段详情：按 `chunk_id` 获取全文

响应约定：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

---

## 6. 会话级状态隔离

后端必须保证以下隔离行为（对应前端现状）：

- 每个 `session_id` 独立绑定一个知识库
- 每个会话的召回参数、结果、最近查询互不污染
- 会话删除时，联动清理关联关系

---

## 7. 环境变量与配置规范

已存在关键变量（见 `.env`）：

- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `DASHSCOPE_API_KEY`
- `milvus_url`

要求：

1. 启动时校验必填 key  
2. 对重复 key（如多个 `OPENAI_API_KEY`）给出明确优先级策略  
3. 模型路由统一经 `ModelRouter` 管理，不允许在业务代码散落判断

---

## 8. 错误码与异常处理

建议最小错误码集：

- `1001` 参数校验失败
- `1002` 资源不存在
- `1003` 状态冲突（构建中重复操作）
- `2001` 文件格式不支持
- `3001` 检索失败
- `3002` 重排失败
- `3003` 模型调用失败

日志要求：

- 请求链路追踪 ID
- 构建任务每阶段耗时
- 模型调用耗时与错误原因（脱敏）

---

## 9. 测试与验收

## 9.1 测试层次

- 单元测试：参数校验、模型路由、结果映射
- 集成测试：上传->构建->召回->问答全链路
- 回归测试：会话切换不串状态、删除联动正确

## 9.2 验收标准（后端）

1. 任一会话可独立创建并绑定知识库  
2. 构建阶段状态与进度可查询  
3. 召回测试返回 `initial_results` + `final_results`  
4. 聊天返回 `[1][2][3]` 引用与来源映射  
5. 所有接口字段与 `frontend-api-contract.md` 对齐

---

## 10. 实施里程碑建议

### M1：基础骨架

- FastAPI 项目初始化
- 配置系统、响应封装、错误码

### M2：RAG 构建链路

- 上传文件
- LlamaIndex ingest + Milvus 入库
- 构建任务轮询

### M3：检索与问答

- 召回测试接口（Top-N/Top-K）
- 聊天接口（含引用）

### M4：Agent 化

- LangChain Tool 封装
- LangGraph 条件流程

### M5：联调收尾

- 前后端字段全量对齐
- 回归与性能基线

---

## 11. 关联文档

- `llama-index-rag-usage.md`
- `langchain-agent-tooling-usage.md`
- `frontend-api-contract.md`
- `backend-frontend-field-mapping.md`
- `agentic-rag-frontend-requirements.md`
