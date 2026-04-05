from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.schemas.knowledge_base import KBFile, KnowledgeBase


class KnowledgeBaseService:
    def __init__(self) -> None:
        self._kbs: dict[str, KnowledgeBase] = {}
        self._file_paths: dict[str, str] = {}
        self._task_results: dict[str, dict[str, int]] = {}
        self._chunk_details: dict[str, dict[str, str | float]] = {}
        self._kb_chunk_ids: dict[str, set[str]] = {}

    def create_knowledge_base(
        self,
        name: str,
        chunk_size: int,
        chunk_overlap: int,
        file_name: str,
        file_size: Optional[int],
        mime_type: Optional[str],
    ) -> KnowledgeBase:
        now = datetime.now(timezone.utc)
        kb_id = f"kb_{uuid4().hex[:8]}"
        file_id = f"file_{uuid4().hex[:8]}"

        kb_file = KBFile(
            id=file_id,
            filename=file_name,
            size=file_size,
            mime_type=mime_type,
            status="uploaded",
            uploaded_at=now,
        )
        kb = KnowledgeBase(
            id=kb_id,
            name=name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            status="building",
            files=[kb_file],
            created_at=now,
            updated_at=now,
        )
        self._kbs[kb_id] = kb
        return kb

    def get_knowledge_base(self, knowledge_base_id: str) -> Optional[KnowledgeBase]:
        return self._kbs.get(knowledge_base_id)

    def set_file_path(self, file_id: str, file_path: str) -> None:
        self._file_paths[file_id] = file_path

    def get_file_path(self, file_id: str) -> Optional[str]:
        return self._file_paths.get(file_id)

    def get_file_paths(self, knowledge_base_id: str) -> list[str]:
        kb = self._kbs.get(knowledge_base_id)
        if kb is None:
            return []
        paths: list[str] = []
        for item in kb.files:
            file_path = self._file_paths.get(item.id)
            if file_path:
                paths.append(file_path)
        return paths

    def set_task_result(self, task_id: str, result: dict[str, int]) -> None:
        self._task_results[task_id] = result

    def get_task_result(self, task_id: str) -> Optional[dict[str, int]]:
        return self._task_results.get(task_id)

    def set_chunk_details(self, knowledge_base_id: str, chunks: list[dict[str, str | float]]) -> None:
        existing = self._kb_chunk_ids.get(knowledge_base_id, set())
        for chunk_id in existing:
            self._chunk_details.pop(chunk_id, None)
        next_ids: set[str] = set()
        for item in chunks:
            chunk_id = str(item["chunk_id"])
            self._chunk_details[chunk_id] = item
            next_ids.add(chunk_id)
        self._kb_chunk_ids[knowledge_base_id] = next_ids

    def get_chunk_detail(self, chunk_id: str) -> Optional[dict[str, str | float]]:
        return self._chunk_details.get(chunk_id)

    def get_chunk_detail_in_kb(self, knowledge_base_id: str, chunk_id: str) -> Optional[dict[str, str | float]]:
        if chunk_id not in self._kb_chunk_ids.get(knowledge_base_id, set()):
            return None
        return self._chunk_details.get(chunk_id)

    def set_knowledge_base_status(self, knowledge_base_id: str, status: str) -> None:
        kb = self._kbs.get(knowledge_base_id)
        if kb is None:
            return
        kb.status = status  # type: ignore[assignment]
        kb.updated_at = datetime.now(timezone.utc)
        self._kbs[knowledge_base_id] = kb

    def set_file_status(self, knowledge_base_id: str, file_id: str, status: str) -> None:
        kb = self._kbs.get(knowledge_base_id)
        if kb is None:
            return
        for item in kb.files:
            if item.id == file_id:
                item.status = status  # type: ignore[assignment]
                break
        kb.updated_at = datetime.now(timezone.utc)
        self._kbs[knowledge_base_id] = kb

    def append_file(
        self,
        knowledge_base_id: str,
        file_name: str,
        file_size: Optional[int],
        mime_type: Optional[str],
    ) -> Optional[str]:
        kb = self._kbs.get(knowledge_base_id)
        if kb is None:
            return None

        now = datetime.now(timezone.utc)
        new_file = KBFile(
            id=f"file_{uuid4().hex[:8]}",
            filename=file_name,
            size=file_size,
            mime_type=mime_type,
            status="uploaded",
            uploaded_at=now,
        )
        kb.files.append(new_file)
        kb.status = "building"
        kb.updated_at = now
        self._kbs[knowledge_base_id] = kb
        return new_file.id

    def delete_knowledge_base(self, knowledge_base_id: str) -> bool:
        kb = self._kbs.get(knowledge_base_id)
        if kb is None:
            return False
        for item in kb.files:
            self._file_paths.pop(item.id, None)
        for chunk_id in self._kb_chunk_ids.get(knowledge_base_id, set()):
            self._chunk_details.pop(chunk_id, None)
        self._kb_chunk_ids.pop(knowledge_base_id, None)
        del self._kbs[knowledge_base_id]
        return True

    def delete_file(self, knowledge_base_id: str, file_id: str) -> Optional[int]:
        kb = self._kbs.get(knowledge_base_id)
        if kb is None:
            return None

        next_files = [item for item in kb.files if item.id != file_id]
        if len(next_files) == len(kb.files):
            return None

        kb.files = next_files
        kb.updated_at = datetime.now(timezone.utc)
        self._kbs[knowledge_base_id] = kb
        self._file_paths.pop(file_id, None)
        return len(next_files)


knowledge_base_service = KnowledgeBaseService()
