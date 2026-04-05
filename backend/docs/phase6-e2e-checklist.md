# Phase6 联调回归清单（E2E + 稳定性）

本文档用于收敛当前 Phase6（联调回归）剩余任务，覆盖多模型、多检索模式、流式输出与异常场景。

## 1) 自动化回归（已完成）

- 脚本路径：`backend/scripts/phase6_regression.py`
- 运行方式（在 `backend` 目录）：
  - `./.venv/bin/python scripts/phase6_regression.py`
- 当前覆盖：
  - `chat/completions` 正常返回（`mode=none`）
  - `chat/completions` 参数越界（`top_k > top_n`）
  - `chat/completions` 会话不存在
  - `chat/completions` 缺少知识库拦截（`mode!=none`）
  - `chat/completions/stream` SSE 事件完整性（`meta/delta/done`）
  - `chat/completions/stream` 参数越界（`top_k > top_n`）
  - `chat/completions/stream` 缺少知识库拦截（`mode!=none`）
  - `chat/completions/stream` 流中断错误事件（`event:error`）
- 最新执行结果：`8/8 PASS`

## 2) 手工联调清单（建议逐项打勾）

- [x] DeepSeek + `none`：验证纯生成回答（已通过）
- [x] DeepSeek + `vector`：验证 Top-N/Top-K 与片段详情一致（已通过）
- [x] DeepSeek + `hybrid`：验证 RRF 排序稳定，分数不因 BM25 量纲异常失真（已通过）
- [x] DeepSeek + `hybrid_rerank`：验证 Top-K 精排结果与引用标记一致（已通过）
- [x] OpenAI + `hybrid_rerank`：验证模型路由与返回结构稳定（已通过）
- [x] DashScope + `hybrid_rerank`：验证路由正确、流式增量显示正常（已通过）

## 3) 流式稳定性清单

- [x] 网络抖动时前端能展示错误，不出现“永远加载中”（通过 `event:error` 路径验证）
- [x] 用户快速连续发送 2 次消息，不会串流到同一气泡（已实测通过）
- [x] 召回为空时仍可流式返回可解释回答（如“知识不足”）（`mode=none` 与空上下文路径通过）
- [x] 长回答场景下前端仍可持续增量渲染，不出现卡顿（已实测通过）

## 4) 上线前检查

- [x] `.env` 中三路模型 Key/URL/Model 均已配置且有效
- [x] 后端服务重启后 `chat/completions` 与 `chat/completions/stream` 均可访问
- [x] 前端问答区可见实时流式光标与最终引用列表
- [x] 回归脚本最近一次执行结果为全 PASS
