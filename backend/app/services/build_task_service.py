from datetime import datetime, timezone
from threading import Lock
from threading import Thread
from typing import Any
from typing import Callable
from typing import Optional
from uuid import uuid4

from app.schemas.build_task import BuildTask


TaskRunner = Callable[[str, dict[str, Any]], None]


class BuildTaskService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._tasks: dict[str, BuildTask] = {}
        self._payloads: dict[str, dict[str, Any]] = {}
        self._runners: dict[str, TaskRunner] = {}

    def create_task(
        self,
        knowledge_base_id: str,
        runner: TaskRunner,
        payload: dict[str, Any],
    ) -> BuildTask:
        now = datetime.now(timezone.utc)
        task_id = f"task_{uuid4().hex[:8]}"
        task = BuildTask(
            task_id=task_id,
            knowledge_base_id=knowledge_base_id,
            stage="uploaded",
            progress=5,
            error_message=None,
            updated_at=now,
        )
        with self._lock:
            self._tasks[task_id] = task
            self._payloads[task_id] = payload
            self._runners[task_id] = runner
        self._start_task(task_id=task_id)
        return task

    def get_task(self, task_id: str) -> Optional[BuildTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def retry_task(self, task_id: str) -> Optional[BuildTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.stage != "failed":
                raise ValueError("task is not in failed state")
            task.stage = "uploaded"
            task.progress = 5
            task.error_message = None
            task.updated_at = datetime.now(timezone.utc)
            self._tasks[task_id] = task
            payload = self._payloads.get(task_id)
            if payload is not None:
                # Retry assumes caller has fixed the root cause.
                payload["should_fail"] = False
                self._payloads[task_id] = payload
        self._start_task(task_id=task_id)
        return self.get_task(task_id)

    def update_task(self, task_id: str, stage: str, progress: int, error_message: Optional[str] = None) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.stage = stage  # type: ignore[assignment]
            task.progress = progress
            task.error_message = error_message
            task.updated_at = datetime.now(timezone.utc)
            self._tasks[task_id] = task

    def _start_task(self, task_id: str) -> None:
        thread = Thread(target=self._run_task, args=(task_id,), daemon=True)
        thread.start()

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            runner = self._runners.get(task_id)
            payload = self._payloads.get(task_id)
        if runner is None or payload is None:
            self.update_task(task_id=task_id, stage="failed", progress=100, error_message="task payload missing")
            return
        runner(task_id, payload)


build_task_service = BuildTaskService()
