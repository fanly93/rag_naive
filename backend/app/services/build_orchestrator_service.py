import time
from typing import Any

from app.core.config import get_settings
from app.schemas.build_task import BuildTask
from app.services.build_task_service import build_task_service
from app.services.knowledge_base_service import knowledge_base_service
from app.services.rag_ingest_service import rag_ingest_service
from app.services.session_service import session_service


class BuildOrchestratorService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def enqueue_create_build(
        self,
        session_id: str,
        knowledge_base_id: str,
        file_id: str,
        should_fail: bool = False,
    ) -> BuildTask:
        return build_task_service.create_task(
            knowledge_base_id=knowledge_base_id,
            runner=self._run_build_task,
            payload={
                "kind": "create",
                "session_id": session_id,
                "knowledge_base_id": knowledge_base_id,
                "file_id": file_id,
                "should_fail": should_fail,
            },
        )

    def enqueue_append_build(self, knowledge_base_id: str, file_id: str, should_fail: bool = False) -> BuildTask:
        return build_task_service.create_task(
            knowledge_base_id=knowledge_base_id,
            runner=self._run_build_task,
            payload={
                "kind": "append",
                "knowledge_base_id": knowledge_base_id,
                "file_id": file_id,
                "should_fail": should_fail,
            },
        )

    def get_task(self, task_id: str) -> BuildTask | None:
        return build_task_service.get_task(task_id)

    def retry_task(self, task_id: str) -> BuildTask | None:
        return build_task_service.retry_task(task_id)

    def _run_build_task(self, task_id: str, payload: dict[str, Any]) -> None:
        kb_id = str(payload["knowledge_base_id"])
        file_id = str(payload["file_id"])
        session_id = str(payload.get("session_id", ""))
        kind = str(payload.get("kind", "append"))
        should_fail = bool(payload.get("should_fail", False))

        try:
            knowledge_base_service.set_knowledge_base_status(knowledge_base_id=kb_id, status="building")
            knowledge_base_service.set_file_status(knowledge_base_id=kb_id, file_id=file_id, status="indexing")

            build_task_service.update_task(task_id=task_id, stage="chunking", progress=30)
            time.sleep(0.2)

            kb = knowledge_base_service.get_knowledge_base(kb_id)
            if kb is None:
                raise ValueError("knowledge base not found")
            if should_fail:
                raise RuntimeError("forced build failure for retry test")

            file_paths = knowledge_base_service.get_file_paths(kb_id)
            if not file_paths:
                raise ValueError("knowledge base has no files on disk")

            build_task_service.update_task(task_id=task_id, stage="indexing", progress=60)
            node_count = rag_ingest_service.split_only(kb=kb, file_paths=file_paths)

            build_task_service.update_task(task_id=task_id, stage="vectorizing", progress=90)
            time.sleep(0.2)
            if not self._settings.task_simulate_build:
                rag_ingest_service.build_index(kb=kb, file_paths=file_paths)

            knowledge_base_service.set_file_status(knowledge_base_id=kb_id, file_id=file_id, status="ready")
            knowledge_base_service.set_knowledge_base_status(knowledge_base_id=kb_id, status="ready")
            if kind == "create":
                session_service.bind_knowledge_base(session_id=session_id, knowledge_base_id=kb_id)

            build_task_service.update_task(task_id=task_id, stage="done", progress=100, error_message=None)
            knowledge_base_service.set_task_result(task_id=task_id, result={"node_count": node_count})
        except Exception as exc:
            knowledge_base_service.set_file_status(knowledge_base_id=kb_id, file_id=file_id, status="failed")
            knowledge_base_service.set_knowledge_base_status(knowledge_base_id=kb_id, status="failed")
            build_task_service.update_task(task_id=task_id, stage="failed", progress=100, error_message=str(exc))


build_orchestrator_service = BuildOrchestratorService()
