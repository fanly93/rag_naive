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

    def fake_complete(**_: object) -> tuple[str, str, str]:
        return "这是回归脚本返回的测试回答 [1]", "deepseek", "deepseek-chat"

    def fake_stream_complete(**_: object):
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

        for name, fn in [
            ("chat/completions 正常返回", case_chat_completion_mode_none),
            ("chat/completions 参数越界拦截", case_chat_completion_invalid_topk),
            ("chat/completions 会话不存在", case_chat_completion_missing_session),
            ("chat/completions 缺少知识库拦截", case_chat_completion_mode_requires_kb),
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
