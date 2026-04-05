from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

from fastapi.testclient import TestClient

# Ensure `app` package can be imported when script runs from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.services.chat_service import chat_service


@dataclass
class CaseResult:
    name: str
    passed: bool
    detail: str = ""


def _run_case(name: str, fn: Callable[[], None]) -> CaseResult:
    try:
        fn()
        return CaseResult(name=name, passed=True, detail="ok")
    except Exception as exc:  # noqa: BLE001 - regression runner should capture all
        return CaseResult(name=name, passed=False, detail=str(exc))


def main() -> None:
    client = TestClient(app)

    # Create a valid session for positive-path tests.
    created = client.post("/api/v1/sessions", json={"title": "phase6-regression"})
    assert created.status_code == 201, created.text
    session_id = created.json()["data"]["id"]

    original_complete = chat_service.complete
    original_stream_complete = chat_service.stream_complete
    complete_calls: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> tuple[str, str, str]:
        complete_calls.append(dict(kwargs))
        return "这是回归脚本返回的测试回答 [1]", "deepseek", "deepseek-chat"

    def fake_stream_complete(**kwargs: object):
        def gen():
            yield "这是"
            yield "流式"
            yield "回答"

        return gen(), "deepseek", "deepseek-chat"

    chat_service.complete = fake_complete  # type: ignore[assignment]
    chat_service.stream_complete = fake_stream_complete  # type: ignore[assignment]

    try:
        results: list[CaseResult] = []

        def case_chat_completion_mode_none() -> None:
            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": session_id,
                    "query": "什么是RAG",
                    "mode": "none",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()["data"]
            assert "测试回答" in body["answer"]
            assert body["initial_results"] == []
            assert body["final_results"] == []

        def case_chat_completion_invalid_topk() -> None:
            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": session_id,
                    "query": "什么是RAG",
                    "mode": "none",
                    "top_n": 2,
                    "top_k": 3,
                },
            )
            assert resp.status_code == 400, resp.text

        def case_chat_completion_missing_session() -> None:
            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": "sess_not_exists",
                    "query": "什么是RAG",
                    "mode": "none",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert resp.status_code == 404, resp.text

        def case_chat_stream_sse() -> None:
            with client.stream(
                "POST",
                "/api/v1/chat/completions/stream",
                json={
                    "session_id": session_id,
                    "query": "什么是RAG",
                    "mode": "none",
                    "top_n": 5,
                    "top_k": 3,
                },
            ) as resp:
                assert resp.status_code == 200, resp.text
                text = "".join(resp.iter_text())
                assert "event: meta" in text
                assert "event: delta" in text
                assert "event: done" in text
                assert "流式" in text

        def case_chat_stream_invalid_topk() -> None:
            resp = client.post(
                "/api/v1/chat/completions/stream",
                json={
                    "session_id": session_id,
                    "query": "什么是RAG",
                    "mode": "none",
                    "top_n": 1,
                    "top_k": 3,
                },
            )
            assert resp.status_code == 400, resp.text

        def case_chat_completion_mode_requires_kb() -> None:
            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": session_id,
                    "query": "什么是RAG",
                    "mode": "hybrid",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert resp.status_code == 400, resp.text

        def case_chat_stream_mode_requires_kb() -> None:
            resp = client.post(
                "/api/v1/chat/completions/stream",
                json={
                    "session_id": session_id,
                    "query": "什么是RAG",
                    "mode": "hybrid_rerank",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert resp.status_code == 400, resp.text

        def case_chat_stream_error_event() -> None:
            current_stream = chat_service.stream_complete

            def broken_stream_complete(**_: object):
                def gen():
                    yield "开始"
                    raise RuntimeError("mock stream broken")

                return gen(), "deepseek", "deepseek-chat"

            chat_service.stream_complete = broken_stream_complete  # type: ignore[assignment]
            try:
                with client.stream(
                    "POST",
                    "/api/v1/chat/completions/stream",
                    json={
                        "session_id": session_id,
                        "query": "什么是RAG",
                        "mode": "none",
                        "top_n": 5,
                        "top_k": 3,
                    },
                ) as resp:
                    assert resp.status_code == 200, resp.text
                    text = "".join(resp.iter_text())
                    assert "event: error" in text
            finally:
                chat_service.stream_complete = current_stream  # type: ignore[assignment]

        def case_chat_completion_multiturn_history() -> None:
            complete_calls.clear()
            created_local = client.post("/api/v1/sessions", json={"title": "phase6-memory"})
            assert created_local.status_code == 201, created_local.text
            local_session = created_local.json()["data"]["id"]

            first = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": local_session,
                    "query": "第一轮用户问题",
                    "mode": "none",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert first.status_code == 200, first.text

            second = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": local_session,
                    "query": "第二轮用户问题",
                    "mode": "none",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert second.status_code == 200, second.text
            assert len(complete_calls) >= 2
            second_call = complete_calls[-1]
            history_messages = second_call.get("history_messages")
            assert isinstance(history_messages, list)
            assert any(
                isinstance(item, dict) and item.get("content") == "第一轮用户问题"
                for item in history_messages
            )
            assert any(
                isinstance(item, dict) and "测试回答" in str(item.get("content", ""))
                for item in history_messages
            )

        def case_chat_completion_session_isolation() -> None:
            complete_calls.clear()
            created_a = client.post("/api/v1/sessions", json={"title": "phase6-iso-a"})
            created_b = client.post("/api/v1/sessions", json={"title": "phase6-iso-b"})
            assert created_a.status_code == 201, created_a.text
            assert created_b.status_code == 201, created_b.text
            session_a = created_a.json()["data"]["id"]
            session_b = created_b.json()["data"]["id"]

            resp_a = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": session_a,
                    "query": "这是A会话的问题",
                    "mode": "none",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert resp_a.status_code == 200, resp_a.text

            resp_b = client.post(
                "/api/v1/chat/completions",
                json={
                    "session_id": session_b,
                    "query": "这是B会话的问题",
                    "mode": "none",
                    "top_n": 5,
                    "top_k": 3,
                },
            )
            assert resp_b.status_code == 200, resp_b.text
            assert len(complete_calls) >= 2
            b_history = complete_calls[-1].get("history_messages")
            assert isinstance(b_history, list)
            assert not any(
                isinstance(item, dict) and "A会话" in str(item.get("content", ""))
                for item in b_history
            )
            assert len(b_history) == 0

        for name, fn in [
            ("chat/completions 正常返回", case_chat_completion_mode_none),
            ("chat/completions 参数越界拦截", case_chat_completion_invalid_topk),
            ("chat/completions 会话不存在", case_chat_completion_missing_session),
            ("chat/completions 缺少知识库拦截", case_chat_completion_mode_requires_kb),
            ("chat/completions 多轮历史注入", case_chat_completion_multiturn_history),
            ("chat/completions 会话历史隔离", case_chat_completion_session_isolation),
            ("chat/completions/stream SSE事件流", case_chat_stream_sse),
            ("chat/completions/stream 参数越界拦截", case_chat_stream_invalid_topk),
            ("chat/completions/stream 缺少知识库拦截", case_chat_stream_mode_requires_kb),
            ("chat/completions/stream 流中断错误事件", case_chat_stream_error_event),
        ]:
            results.append(_run_case(name, fn))
    finally:
        chat_service.complete = original_complete  # type: ignore[assignment]
        chat_service.stream_complete = original_stream_complete  # type: ignore[assignment]

    failed = [item for item in results if not item.passed]
    passed = [item for item in results if item.passed]

    print("=== Phase6 Regression Result ===")
    print(f"passed: {len(passed)}")
    print(f"failed: {len(failed)}")
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"[{status}] {item.name} -> {item.detail}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
