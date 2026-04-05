# LlamaIndex 用法整理（RAG 构建四阶段）

本文档聚焦你当前后端任务的第 1 个 to-do：  
整理 **LlamaIndex 在 RAG 主体中的核心用法**，覆盖：

1. 读取文件  
2. 文档切分  
3. 词向量化  
4. Milvus 入库与检索

> 说明：以下内容基于 LlamaIndex 官方仓库示例和文档片段整理，偏工程落地写法，便于后续直接迁移到 FastAPI 后端。

---

## 1. 推荐安装方式（按需集成）

LlamaIndex 官方建议两种模式：

- Starter：`llama-index`（包含 core + 一些常用集成）
- Customized：`llama-index-core` + 你所需的 integrations（更适合生产）

针对你的场景（Milvus + 多模型），建议使用 **Customized**：

```bash
pip install llama-index-core
pip install llama-index-vector-stores-milvus
```

后续再按模型供应商补 llm/embedding/rerank 集成包。

---

## 2. 阶段一：读取文件（Document Loading）

### 2.1 基础目录读取

```python
from llama_index.core import SimpleDirectoryReader

documents = SimpleDirectoryReader("./data").load_data()
```

### 2.2 指定文件提取器（如 PDF）

```python
from llama_index.core import SimpleDirectoryReader

reader = SimpleDirectoryReader(
    input_dir="./uploads",
    # 示例：可按后缀配置专用 reader
    # file_extractor={".pdf": custom_pdf_reader},
)
documents = reader.load_data()
```

工程建议：

- 每个 `Document` 保留元数据（文件名、上传时间、会话/知识库 ID）
- 对空文档、乱码、超大文件先做前置校验

---

## 3. 阶段二：切分（Chunking / Node Parsing）

LlamaIndex 推荐用 `SentenceSplitter` 做语义友好的文本切分。

```python
from llama_index.core.node_parser import SentenceSplitter

splitter = SentenceSplitter(
    chunk_size=1024,
    chunk_overlap=20,
)
nodes = splitter.get_nodes_from_documents(documents)
```

你当前前端参数已对齐：

- `chunk_size`（默认 1024，可调）
- `chunk_overlap`（默认 100，可调）

也可以走全局设置：

```python
from llama_index.core import Settings
from llama_index.core.node_parser import SentenceSplitter

Settings.text_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=100)
```

工程建议：

- 切分后为每个节点补 `metadata`：`kb_id / file_id / chunk_index`
- 后续引用展示（[1][2][3]）依赖这些可追溯字段

---

## 4. 阶段三：词向量化（Embedding）

最常见路径是构建 `VectorStoreIndex` 时自动触发 embedding。  
你可通过 `Settings.embed_model` 或 `from_documents(..., embed_model=...)` 注入模型。

```python
from llama_index.core import VectorStoreIndex

# 方式1：直接 from_documents（内部会做 embedding）
index = VectorStoreIndex.from_documents(documents)
```

或（更可控）：

```python
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_documents(
    documents=documents,
    transformations=[splitter],  # 使用你自定义切分器
    # embed_model=your_embedding_model,  # 建议明确注入
)
```

你项目目标里的 embedding 默认模型是 DashScope `text-embedding-v4`，  
后续实现时只需把 `your_embedding_model` 替换为对应 provider 实例。

---

## 5. 阶段四：Milvus 入库（Vector Store）

LlamaIndex + Milvus 的标准结构是：

1. 建 `MilvusVectorStore`
2. 建 `StorageContext`
3. 用 `VectorStoreIndex.from_documents(...)` 或 `VectorStoreIndex(nodes, ...)` 入库

示例：

```python
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.milvus import MilvusVectorStore

vector_store = MilvusVectorStore(
    uri="http://127.0.0.1:19530",   # 你的 .env 已有 milvus_url
    collection_name="kb_demo",
    dim=1536,                        # 需与 embedding 维度一致
    overwrite=False,
)

storage_context = StorageContext.from_defaults(vector_store=vector_store)

index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
)
```

> 关键点：`dim` 必须与 embedding 模型输出维度一致，否则会入库失败。

---

## 6. 检索与问答（入库后）

最小可用检索问答：

```python
query_engine = index.as_query_engine()
resp = query_engine.query("你的问题")
print(resp)
```

在你的系统里，`as_query_engine()` 的能力会进一步封装为：

- 召回测试（Top-N/Top-K、模式切换）
- 供 LangChain Agent 调用的工具函数

---

## 7. 与你现有需求对齐的参数映射

前端参数 -> LlamaIndex/Milvus 后端参数建议：

- `knowledge_base_name` -> `collection_name`（可加前缀，如 `kb_{id}`）
- `chunk_size` -> `SentenceSplitter(chunk_size=...)`
- `chunk_overlap` -> `SentenceSplitter(chunk_overlap=...)`
- `top_n` -> retriever 候选数量
- `top_k` -> 最终返回/重排后数量
- `mode`:
  - `vector`：纯向量检索
  - `hybrid`：向量 + 稀疏（BM25）
  - `hybrid_rerank`：hybrid 后再 rerank

---

## 8. 常见坑位（先规避）

- `Milvus dim` 与 embedding 维度不一致
- 文档读取后 metadata 丢失，导致引用溯源困难
- chunk 太大导致召回噪声高，太小导致语义断裂
- 未做构建任务状态分阶段（uploaded/chunking/indexing/vectorizing）

---

## 9. 后续可直接进入的实现点

基于本用法文档，下一步可实现：

1. `rag/ingest_service.py`：读取 + 切分 + 向量化 + 入库  
2. `rag/retrieve_service.py`：vector/hybrid/hybrid_rerank 检索  
3. `rag/query_engine_tool.py`：暴露给 LangChain 的 Tool 包装

---

## 参考来源

- LlamaIndex 官方仓库（README 与示例总入口）：[run-llama/llama_index](https://github.com/run-llama/llama_index)
- LlamaIndex `VectorStoreIndex` 基础示例（SimpleDirectoryReader + from_documents）
- LlamaIndex Node Parser / SentenceSplitter 用法
- LlamaIndex MilvusVectorStore 示例（`MilvusVectorStore + StorageContext + VectorStoreIndex`）
