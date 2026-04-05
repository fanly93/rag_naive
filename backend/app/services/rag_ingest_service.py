from pathlib import Path

from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.milvus import MilvusVectorStore

from app.core.config import get_settings
from app.schemas.knowledge_base import KnowledgeBase
from app.services.rag_embedding import DeterministicEmbedding


class RagIngestService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._upload_root = Path(self._settings.upload_root)
        self._upload_root.mkdir(parents=True, exist_ok=True)

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

    def build_index(self, kb: KnowledgeBase, file_paths: list[str]) -> int:
        if not file_paths:
            raise ValueError("knowledge base has no files on disk")

        Settings.embed_model = DeterministicEmbedding(dimension=self._settings.embedding_dim)

        documents = SimpleDirectoryReader(input_files=file_paths).load_data()
        splitter = SentenceSplitter(chunk_size=kb.chunk_size, chunk_overlap=kb.chunk_overlap)
        nodes = splitter.get_nodes_from_documents(documents)
        if not nodes:
            raise ValueError("no nodes generated from uploaded files")

        vector_store = MilvusVectorStore(
            uri=self._settings.milvus_url,
            collection_name=f"kb_{kb.id}",
            dim=self._settings.embedding_dim,
            overwrite=True,
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex(nodes=nodes, storage_context=storage_context)
        return len(nodes)


rag_ingest_service = RagIngestService()
