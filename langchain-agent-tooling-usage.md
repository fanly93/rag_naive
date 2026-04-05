# LangChain 封装 LlamaIndex 工具并创建 Agent（实操文档）

本文档对应后端 to-do 第 2 项：  
将已构建的 LlamaIndex RAG 能力封装成 LangChain 可调用工具，并创建 Agentic RAG 流程。

目标：

1. 把 LlamaIndex 查询能力抽象成 Tool  
2. 让 Agent 自动决定是否调用该 Tool  
3. 支持多模型路由（DeepSeek/OpenAI/DashScope）  
4. 对齐你前端的 `mode/top_n/top_k/引用` 交互

---

## 1. 推荐技术路线

你的场景建议采用：

- **RAG 主体**：LlamaIndex（读取、切分、索引、检索、重排）
- **Agent 编排**：LangChain + LangGraph（可控性强）

建议分层如下：

- `rag/`：LlamaIndex 检索与重排能力（已有/待实现）
- `agent/tools/`：把 rag 能力包装为 LangChain Tool
- `agent/graph/`：LangGraph 节点与流程编排
- `api/`：FastAPI 接口层，调用 graph/service

---

## 2. Tool 设计（核心）

## 2.1 输入输出协议（必须稳定）

建议统一 Tool 入参：

```json
{
  "query": "用户问题",
  "session_id": "sess_001",
  "mode": "vector|hybrid|hybrid_rerank",
  "top_n": 20,
  "top_k": 3
}
```

Tool 出参建议：

```json
{
  "answer": "基于检索的回答草稿（可选）",
  "final_results": [
    {
      "chunk_id": "ch_101",
      "source": "doc.pdf",
      "score": 0.95,
      "content": "..."
    }
  ],
  "initial_results": [
    {
      "chunk_id": "ch_001",
      "source": "doc.pdf",
      "score": 0.88,
      "content": "..."
    }
  ]
}
```

说明：

- `final_results`：对应前端 Top-K 默认展示与问答引用
- `initial_results`：对应前端 Top-N 折叠下拉

---

## 3. 将 LlamaIndex 检索封装成 Tool

## 3.1 Tool 函数（推荐）

```python
from langchain.tools import tool
from pydantic import BaseModel, Field


class RAGToolInput(BaseModel):
    query: str = Field(..., description="用户问题")
    session_id: str = Field(..., description="会话ID")
    mode: str = Field(..., description="vector|hybrid|hybrid_rerank")
    top_n: int = Field(20, ge=1)
    top_k: int = Field(3, ge=1)


@tool(args_schema=RAGToolInput)
def query_knowledge_base(
    query: str,
    session_id: str,
    mode: str,
    top_n: int = 20,
    top_k: int = 3,
) -> dict:
    """
    供 Agent 调用的 RAG 检索工具：
    - 内部调用 LlamaIndex service
    - 返回初召回与最终结果，供前端引用展示
    """
    # 这里调用你自己的 rag service（伪代码）
    result = rag_service.retrieve(
        query=query,
        session_id=session_id,
        mode=mode,
        top_n=top_n,
        top_k=top_k,
    )
    return result
```

---

## 4. Agent 创建（两种可选）

## 4.1 方案A：LangGraph（推荐）

适用：你需要“可控流程 + 条件分支 + 可追踪状态”。

核心流程：

1. `agent_decide`：模型先判断是否调用 `query_knowledge_base`  
2. `retrieve`：如果调用工具，则拿到检索结果  
3. `grade`（可选）：判断结果是否相关  
4. `generate_answer`：最终回答 + 引用映射

伪代码：

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

workflow = StateGraph(MessagesState)
workflow.add_node("agent_decide", agent_decide_node)
workflow.add_node("retrieve", ToolNode([query_knowledge_base]))
workflow.add_node("generate_answer", generate_answer_node)

workflow.add_edge(START, "agent_decide")
workflow.add_conditional_edges(
    "agent_decide",
    tools_condition,
    {"tools": "retrieve", END: END},
)
workflow.add_edge("retrieve", "generate_answer")
workflow.add_edge("generate_answer", END)
graph = workflow.compile()
```

---

## 4.2 方案B：create_agent / ReAct（快速）

适用：先快速验证闭环，后续再升级 LangGraph。

思路：把 `query_knowledge_base` 作为唯一核心工具注入 Agent。

---

## 5. 多模型切换（与你需求强绑定）

你要求：

- Chat 默认：`deepseek-chat`
- Embedding：DashScope `text-embedding-v4`
- Rerank：DashScope `qwen3-rerank`
- Chat 可切换：DeepSeek / OpenAI / DashScope

建议实现一个统一工厂：

```python
class ModelRouter:
    def get_chat_model(self, provider: str, model: str | None = None):
        ...

    def get_embed_model(self):
        # 默认 dashscope text-embedding-v4
        ...

    def get_reranker(self):
        # 默认 dashscope qwen3-rerank
        ...
```

配置优先级建议：

1. 请求级参数（若传入 provider/model）
2. 会话级配置（可选）
3. 系统默认（DeepSeek chat）

---

## 6. 与前端交互字段映射

前端当前已实现点，后端需要严格提供：

- 问答回复文本内包含引用标记：`[1][2][3]`
- `top_k` 引用来源列表：每条提供 `chunk_id + preview(前30字符)`
- `top_n` 初召回列表：折叠展开后可查看详情
- 详情弹窗字段：`source/score/hit_mode/content`

建议后端在聊天接口返回：

```json
{
  "assistant_text": "...... 引用标记：[1][2][3]",
  "citations_top_k": [
    {"index": 1, "chunk_id": "ch_101", "preview": "前30字符..."}
  ],
  "citations_top_n": [
    {"index": 1, "chunk_id": "ch_001", "preview": "前30字符..."}
  ]
}
```

---

## 7. 错误处理建议

Tool 与 Agent 层统一错误结构：

```json
{
  "code": 3001,
  "message": "检索失败",
  "details": "milvus timeout"
}
```

建议错误分类：

- 参数错误：`1001`
- 知识库不存在：`1002`
- 检索失败：`3001`
- 重排失败：`3002`
- 模型调用失败：`3003`

---

## 8. 最小联调闭环（建议先做）

1. 前端发起聊天请求（带 mode/top_n/top_k）  
2. Agent 判断并调用 `query_knowledge_base`  
3. 返回 `assistant_text + top_k + top_n`  
4. 前端渲染：
   - 回复正文 `[1][2][3]`
   - Top-K 独立来源框（可点详情）
   - Top-N 折叠下拉（可点详情）

---

## 9. 参考资料

- LangGraph Agentic RAG 教程（Python）：[Build a custom RAG agent with LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- LangChain Python 集成总览：[LangChain Python integrations](https://docs.langchain.com/oss/python/integrations/providers/overview)
- LlamaIndex 官方仓库：[run-llama/llama_index](https://github.com/run-llama/llama_index)

