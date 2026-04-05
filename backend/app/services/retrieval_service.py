import hashlib
import math
import re
from collections import defaultdict

from llama_index.core.node_parser import SentenceSplitter

from app.schemas.knowledge_base import KnowledgeBase
from app.schemas.retrieval import RetrievalChunk
from app.schemas.retrieval import RetrieveMode
from app.services.rag_ingest_service import rag_ingest_service


class RetrievalService:
    def _tokens(self, text: str) -> list[str]:
        normalized = text.lower()
        pieces = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", normalized)
        if not pieces:
            return ["_"]
        return pieces

    def _vector_score(self, query: str, text: str) -> float:
        q = self._tokens(query)
        t = self._tokens(text)
        q_set = set(q)
        t_set = set(t)
        intersect = len(q_set & t_set)
        denom = math.sqrt(max(len(q_set), 1) * max(len(t_set), 1))
        return round(intersect / denom if denom else 0.0, 4)

    def _bm25_like_score(self, query: str, text: str) -> float:
        q = self._tokens(query)
        t = self._tokens(text)
        tf = defaultdict(int)
        for token in t:
            tf[token] += 1
        score = 0.0
        for token in q:
            if tf[token] > 0:
                score += 1.0 + math.log(1.0 + tf[token])
        length_penalty = 1.0 + math.log(1.0 + len(t))
        return round(score / length_penalty, 4)

    def _chunk_id(self, kb_id: str, source: str, index: int, content: str) -> str:
        digest = hashlib.sha1(f"{kb_id}:{source}:{index}:{content}".encode("utf-8")).hexdigest()[:10]
        return f"ch_{digest}"

    def _build_chunks(self, kb: KnowledgeBase, file_paths: list[str], query: str) -> list[dict[str, str | float]]:
        docs = rag_ingest_service.load_documents(file_paths=file_paths)
        splitter = SentenceSplitter(chunk_size=kb.chunk_size, chunk_overlap=kb.chunk_overlap)
        nodes = splitter.get_nodes_from_documents(docs)
        built: list[dict[str, str | float]] = []
        for index, node in enumerate(nodes):
            content = node.get_content().strip()
            if not content:
                continue
            source = str(node.metadata.get("file_name", "unknown"))
            title = f"文档片段{index + 1}"
            vector_score = self._vector_score(query, f"{title} {content}")
            bm25_score = self._bm25_like_score(query, content)
            hybrid_score = round(0.6 * vector_score + 0.4 * bm25_score, 4)
            built.append(
                {
                    "chunk_id": self._chunk_id(kb.id, source, index, content),
                    "title": title,
                    "source": source,
                    "content": content,
                    "vector_score": vector_score,
                    "bm25_score": bm25_score,
                    "hybrid_score": hybrid_score,
                }
            )
        if not built:
            raise ValueError("no chunks generated for retrieval")
        return built

    def retrieve(
        self,
        kb: KnowledgeBase,
        file_paths: list[str],
        query: str,
        mode: RetrieveMode,
        top_n: int,
        top_k: int,
    ) -> tuple[list[RetrievalChunk], list[RetrievalChunk], list[dict[str, str | float]]]:
        all_chunks = self._build_chunks(kb=kb, file_paths=file_paths, query=query)

        vector_sorted = sorted(all_chunks, key=lambda item: float(item["vector_score"]), reverse=True)
        bm25_sorted = sorted(all_chunks, key=lambda item: float(item["bm25_score"]), reverse=True)
        hybrid_sorted = sorted(all_chunks, key=lambda item: float(item["hybrid_score"]), reverse=True)

        initial: list[RetrievalChunk] = []
        if mode == "vector":
            for item in vector_sorted[:top_n]:
                initial.append(
                    RetrievalChunk(
                        chunk_id=str(item["chunk_id"]),
                        title=str(item["title"]),
                        source=str(item["source"]),
                        score=float(item["vector_score"]),
                        content=str(item["content"]),
                        channel="vector",
                        hit_mode="vector",
                    )
                )
        else:
            seen: set[str] = set()
            i = 0
            while len(initial) < top_n and (i < len(vector_sorted) or i < len(bm25_sorted)):
                if i < len(vector_sorted):
                    item = vector_sorted[i]
                    cid = str(item["chunk_id"])
                    if cid not in seen:
                        initial.append(
                            RetrievalChunk(
                                chunk_id=cid,
                                title=str(item["title"]),
                                source=str(item["source"]),
                                score=float(item["vector_score"]),
                                content=str(item["content"]),
                                channel="vector",
                                hit_mode="vector",
                            )
                        )
                        seen.add(cid)
                        if len(initial) >= top_n:
                            break
                if i < len(bm25_sorted):
                    item = bm25_sorted[i]
                    cid = str(item["chunk_id"])
                    if cid not in seen:
                        initial.append(
                            RetrievalChunk(
                                chunk_id=cid,
                                title=str(item["title"]),
                                source=str(item["source"]),
                                score=float(item["bm25_score"]),
                                content=str(item["content"]),
                                channel="bm25",
                                hit_mode="bm25",
                            )
                        )
                        seen.add(cid)
                i += 1

        if mode == "hybrid_rerank":
            initial_index = {item.chunk_id: item for item in initial}
            reranked_source = [item for item in hybrid_sorted if str(item["chunk_id"]) in initial_index][:top_k]
            final = [
                RetrievalChunk(
                    chunk_id=str(item["chunk_id"]),
                    title=str(item["title"]),
                    source=str(item["source"]),
                    score=round(float(item["hybrid_score"]) + 0.03, 4),
                    content=str(item["content"]),
                    channel="rerank",
                    hit_mode=f"rerank(来自 {initial_index[str(item['chunk_id'])].hit_mode})",
                )
                for item in reranked_source
            ]
        else:
            final = initial[:top_k]

        # Keep response order stable: highest relevance first.
        initial = sorted(initial, key=lambda item: item.score, reverse=True)
        final = sorted(final, key=lambda item: item.score, reverse=True)
        return initial, final, all_chunks


retrieval_service = RetrievalService()
