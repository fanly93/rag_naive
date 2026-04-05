from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.db import SessionLocal
from app.models import SessionModel
from app.services.session_service import session_service


@dataclass
class CaseResult:
    name: str
    passed: bool
    detail: str = ""


def run_case(name: str, fn: Callable[[], None]) -> CaseResult:
    try:
        fn()
        return CaseResult(name=name, passed=True, detail="ok")
    except Exception as exc:  # noqa: BLE001
        return CaseResult(name=name, passed=False, detail=str(exc))


def main() -> None:
    client = TestClient(app)
    created_session_id = ""
    results: list[CaseResult] = []

    def case_create_session_api() -> None:
        nonlocal created_session_id
        resp = client.post("/api/v1/sessions", json={"title": "mysql-regression-session", "is_draft": True})
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        created_session_id = body["id"]
        assert created_session_id.startswith("sess_"), body
        assert body["knowledge_base_id"] is None, body

    def case_row_persisted_in_mysql() -> None:
        assert created_session_id, "session not created"
        with SessionLocal() as db:
            row = db.scalar(select(SessionModel).where(SessionModel.id == created_session_id))
        assert row is not None, "session row not found in mysql"
        assert row.title == "mysql-regression-session", row.title

    def case_bind_kb_updates_row() -> None:
        assert created_session_id, "session not created"
        ok = session_service.bind_knowledge_base(created_session_id, "kb_demo1234")
        assert ok is True
        with SessionLocal() as db:
            row = db.scalar(select(SessionModel).where(SessionModel.id == created_session_id))
        assert row is not None
        assert row.knowledge_base_id == "kb_demo1234", row.knowledge_base_id

    def case_delete_session_api() -> None:
        assert created_session_id, "session not created"
        resp = client.delete(f"/api/v1/sessions/{created_session_id}")
        assert resp.status_code == 200, resp.text
        with SessionLocal() as db:
            row = db.scalar(select(SessionModel).where(SessionModel.id == created_session_id))
        assert row is None, "session row still exists after delete"

    for name, fn in [
        ("创建会话接口", case_create_session_api),
        ("会话记录落库校验", case_row_persisted_in_mysql),
        ("绑定知识库写库校验", case_bind_kb_updates_row),
        ("删除会话同步删库校验", case_delete_session_api),
    ]:
        results.append(run_case(name, fn))

    failed = [item for item in results if not item.passed]
    passed = [item for item in results if item.passed]
    print("=== Session MySQL Regression ===")
    print(f"passed: {len(passed)}")
    print(f"failed: {len(failed)}")
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"[{status}] {item.name} -> {item.detail}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
