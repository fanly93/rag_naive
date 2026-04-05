from pathlib import Path

import fitz
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from llama_index.vector_stores.milvus import MilvusVectorStore

from app.core.config import get_settings
from app.schemas.knowledge_base import KnowledgeBase
from app.services.rag_embedding import create_embedding_model


class RagIngestService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._upload_root = Path(self._settings.upload_root)
        self._upload_root.mkdir(parents=True, exist_ok=True)
        self._fallback_milvus_uri = str(self._upload_root.parent / "milvus.db")

    def save_file(
        self,
        session_id: str,
        knowledge_base_id: str,
        file_id: str,
        filename: str,
        content: bytes,
    ) -> Path:
        target_dir = self._upload_root / session_id / knowledge_base_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{file_id}_{Path(filename).name}"
        target_path.write_bytes(content)
        return target_path

    def load_documents(self, file_paths: list[str]) -> list[Document]:
        documents: list[Document] = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue
            text = self._extract_text(path)
            cleaned = self._clean_text(text=text, file_name=path.name)
            documents.append(Document(text=cleaned, metadata={"file_name": path.name}))
        return documents

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            pages: list[str] = []
            with fitz.open(path) as doc:
                for page in doc:
                    pages.append(page.get_text("text") or "")
            return "\n".join(pages)
        return path.read_text(encoding="utf-8", errors="ignore")

    def _clean_text(self, text: str, file_name: str) -> str:
        normalized = text.replace("\x00", "").strip()
        if not normalized:
            raise ValueError(f"file {file_name} has no extractable text")
        printable = sum(1 for ch in normalized if ch.isprintable() or ch in "\n\r\t")
        ratio = printable / max(len(normalized), 1)
        if ratio < 0.85:
            raise ValueError(f"file {file_name} contains too many non-text characters")
        return normalized

    def build_index(self, kb: KnowledgeBase, file_paths: list[str]) -> int:
        if not file_paths:
            raise ValueError("knowledge base has no files on disk")

        Settings.embed_model = create_embedding_model()

        documents = self.load_documents(file_paths=file_paths)
        splitter = SentenceSplitter(chunk_size=kb.chunk_size, chunk_overlap=kb.chunk_overlap)
        nodes = splitter.get_nodes_from_documents(documents)
        if not nodes:
            raise ValueError("no nodes generated from uploaded files")

        try:
            self._index_nodes(kb=kb, nodes=nodes, uri=self._settings.milvus_url)
        except Exception:
            # If remote Milvus is unreachable, fallback to local Milvus Lite file.
            if self._settings.milvus_url.startswith("http"):
                self._index_nodes(kb=kb, nodes=nodes, uri=self._fallback_milvus_uri)
            else:
                raise
        return len(nodes)

    def _index_nodes(self, kb: KnowledgeBase, nodes: list, uri: str) -> None:
        vector_store = MilvusVectorStore(
            uri=uri,
            collection_name=f"kb_{kb.id}",
            dim=self._settings.embedding_dim,
            overwrite=True,
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex(nodes=nodes, storage_context=storage_context)

    def split_only(self, kb: KnowledgeBase, file_paths: list[str]) -> int:
        if not file_paths:
            raise ValueError("knowledge base has no files on disk")
        documents = self.load_documents(file_paths=file_paths)
        splitter = SentenceSplitter(chunk_size=kb.chunk_size, chunk_overlap=kb.chunk_overlap)
        nodes = splitter.get_nodes_from_documents(documents)
        if not nodes:
            raise ValueError("no nodes generated from uploaded files")
        return len(nodes)


rag_ingest_service = RagIngestService()
