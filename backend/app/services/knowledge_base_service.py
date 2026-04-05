from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.schemas.knowledge_base import KBFile, KnowledgeBase


class KnowledgeBaseService:
    def __init__(self) -> None:
        self._kbs: dict[str, KnowledgeBase] = {}
        self._file_paths: dict[str, str] = {}

    def create_knowledge_base(
        self,
        name: str,
        chunk_size: int,
        chunk_overlap: int,
        file_name: str,
        file_size: Optional[int],
        mime_type: Optional[str],
    ) -> tuple[KnowledgeBase, str]:
        now = datetime.now(timezone.utc)
        kb_id = f"kb_{uuid4().hex[:8]}"
        file_id = f"file_{uuid4().hex[:8]}"
        task_id = f"task_{uuid4().hex[:8]}"

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
        return kb, task_id

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
        return f"task_{uuid4().hex[:8]}"

    def delete_knowledge_base(self, knowledge_base_id: str) -> bool:
        kb = self._kbs.get(knowledge_base_id)
        if kb is None:
            return False
        for item in kb.files:
            self._file_paths.pop(item.id, None)
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
