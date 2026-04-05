# Agentic RAG 本地开发项目

一个可本地运行的前后端分离 RAG 系统，用于知识库构建、检索测试与多模型问答。  
当前实现支持会话持久化（MySQL）、向量检索（Milvus/Lite）、混合召回（Vector + BM25 + RRF）与流式回答（SSE）。

## 1. 项目作用

- 支持上传 `txt/md/pdf` 文件，构建知识库并分片索引
- 支持 `vector / hybrid / hybrid_rerank` 多种检索模式
- 支持 `top-n` 初召回 + `top-k` 重排结果
- 支持 `DeepSeek / OpenAI / DashScope` 聊天模型切换
- 支持会话、消息、引用信息持久化到 MySQL
- 支持历史上下文记忆（可配置轮数与单条消息截断长度）

## 2. 技术栈

### 前端

- React 19
- TypeScript
- Vite

### 后端

- FastAPI
- Pydantic Settings
- SQLAlchemy + PyMySQL
- LlamaIndex
- DashScope SDK
- PyMuPDF（PDF 解析）

### 存储与检索

- MySQL（会话/消息/引用持久化）
- Milvus（向量存储）
  - 当配置为远端 Milvus 且不可达时，代码会回退到本地 Milvus Lite 文件

## 3. 目录结构

```text
rag_naive/
├─ frontend/                  # React + Vite 前端
├─ backend/                   # FastAPI 后端
│  ├─ app/
│  │  ├─ api/routes/          # API 路由
│  │  ├─ services/            # 业务服务（检索、问答、会话等）
│  │  ├─ models/              # SQLAlchemy 模型
│  │  └─ core/config.py       # 环境配置读取
│  ├─ docs/
│  │  └─ backend-api-implemented.md
│  └─ requirements.txt
└─ .env                       # 全局环境变量（后端读取）
```

## 4. 环境要求

- Python `3.12`（建议）
- Node.js `18+`（建议）
- MySQL `8+`（本地或 Docker）
- Milvus（可选远端；不可达时可使用 Lite 回退）

## 5. 环境变量配置

后端通过项目根目录 `.env` 读取配置（`backend/app/core/config.py`）。

最小建议配置（示例，替换为你自己的值）：

```bash
# 聊天模型
DEFAULT_CHAT_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_CHAT_MODEL=deepseek-chat

OPENAI_API_KEY=your_openai_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_CHAT_MODEL=gpt-4o-mini

DASHSCOPE_API_KEY=your_dashscope_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen-plus

# Embedding / Rerank
EMBEDDING_MODEL_NAME=text-embedding-v4
RERANK_MODEL_NAME=qwen3-rerank

# Milvus
MILVUS_URL=http://127.0.0.1:19530
# 也可以给本地文件路径（Milvus Lite），例如：
# MILVUS_URL=backend/data/milvus.db

# MySQL（数据库需先创建）
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=agentic_rag
MYSQL_CHARSET=utf8mb4

# RRF 融合权重
RRF_K=60
RRF_VECTOR_WEIGHT=0.7
RRF_BM25_WEIGHT=0.3
RRF_FILE_TYPE_WEIGHTS_JSON={".pdf":{"vector":0.7,"bm25":0.3},".md":{"vector":0.7,"bm25":0.3},".txt":{"vector":0.7,"bm25":0.3}}

# 历史上下文
HISTORY_TURNS_LIMIT=8
HISTORY_MAX_CHARS=1200
```

> 安全提示：请勿将真实 API Key 提交到公开仓库。

## 6. 依赖安装

### 6.1 后端

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 6.2 前端

```bash
cd frontend
npm install
```

## 7. 启动方法

### 7.1 启动后端（FastAPI）

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后可访问：

- 健康检查：`http://127.0.0.1:8000/api/v1/health`
- 根路由：`http://127.0.0.1:8000/`

> 说明：后端启动时会自动连接 MySQL 并执行 `create_all`；但数据库 `agentic_rag` 需预先创建。

### 7.2 启动前端（Vite）

```bash
cd frontend
npm run dev
```

默认地址：

- `http://127.0.0.1:5173`（或 Vite 输出端口）

前端已配置代理：`/api -> http://127.0.0.1:8000`。

## 8. 常用开发命令

### 后端回归（已包含 chat/completions 与 stream 用例）

```bash
cd backend
source .venv/bin/activate
python scripts/phase6_regression.py
```

### 前端构建

```bash
cd frontend
npm run build
```

## 9. 接口文档

- 后端已实现接口说明：`backend/docs/backend-api-implemented.md`
- Phase6 E2E 检查清单：`backend/docs/phase6-e2e-checklist.md`

---

如果你准备继续开发，建议优先检查三项：  
1) MySQL 是否可连通；2) Milvus 地址是否可达；3) `.env` 中模型 Key 是否有效。
