import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import dashscope
from dashscope import TextReRank
from llama_index.core.node_parser import SentenceSplitter

from app.core.config import get_settings
from app.schemas.knowledge_base import KnowledgeBase
from app.schemas.retrieval import RetrievalChunk
from app.schemas.retrieval import RetrieveMode
from app.services.rag_ingest_service import rag_ingest_service


class RetrievalService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._rrf_file_type_weights = self._parse_file_type_weights(
            self._settings.rrf_file_type_weights_json
        )

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

    def _rrf(self, rank: int, k: int = 60) -> float:
        # Reciprocal Rank Fusion: robustly fuses heterogeneous retriever outputs.
        return 1.0 / (k + rank)

    def _normalize_weights(self, vector_weight: float, bm25_weight: float) -> tuple[float, float]:
        total = vector_weight + bm25_weight
        if total <= 0:
            return 0.5, 0.5
        return vector_weight / total, bm25_weight / total

    def _parse_file_type_weights(self, raw: str) -> dict[str, tuple[float, float]]:
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        normalized: dict[str, tuple[float, float]] = {}
        for key, value in parsed.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            vector_weight = value.get("vector")
            bm25_weight = value.get("bm25")
            if not isinstance(vector_weight, (int, float)) or not isinstance(bm25_weight, (int, float)):
                continue
            ext = key.strip().lower()
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized[ext] = self._normalize_weights(float(vector_weight), float(bm25_weight))
        return normalized

    def _rrf_weights_for_source(self, source: str) -> tuple[float, float]:
        ext = Path(source).suffix.lower()
        if ext and ext in self._rrf_file_type_weights:
            return self._rrf_file_type_weights[ext]
        return self._normalize_weights(
            self._settings.rrf_vector_weight,
            self._settings.rrf_bm25_weight,
        )

    def _build_hybrid_rrf(self, all_chunks: list[dict[str, str | float]]) -> list[dict[str, str | float]]:
        vector_sorted = sorted(all_chunks, key=lambda item: float(item["vector_score"]), reverse=True)
        bm25_sorted = sorted(all_chunks, key=lambda item: float(item["bm25_score"]), reverse=True)

        vector_rank = {str(item["chunk_id"]): index + 1 for index, item in enumerate(vector_sorted)}
        bm25_rank = {str(item["chunk_id"]): index + 1 for index, item in enumerate(bm25_sorted)}

        fused: list[dict[str, str | float]] = []
        for item in all_chunks:
            chunk_id = str(item["chunk_id"])
            source = str(item["source"])
            vector_weight, bm25_weight = self._rrf_weights_for_source(source)
            rrf_k = self._settings.rrf_k
            v_score = vector_weight * self._rrf(vector_rank[chunk_id], k=rrf_k)
            b_score = bm25_weight * self._rrf(bm25_rank[chunk_id], k=rrf_k)
            fused_score = round(v_score + b_score, 6)
            dominant_channel = "vector" if v_score >= b_score else "bm25"
            fused.append(
                {
                    "chunk_id": chunk_id,
                    "title": str(item["title"]),
                    "source": source,
                    "content": str(item["content"]),
                    "fused_score": fused_score,
                    "dominant_channel": dominant_channel,
                }
            )
        return sorted(fused, key=lambda item: float(item["fused_score"]), reverse=True)

    def _rerank_with_dashscope(
        self,
        query: str,
        initial: list[RetrievalChunk],
        top_k: int,
    ) -> list[RetrievalChunk]:
        if not initial:
            return []
        if not self._settings.dashscope_api_key:
            raise ValueError("DashScope API key is required for rerank.")
        dashscope.api_key = self._settings.dashscope_api_key
        documents = [item.content for item in initial]
        response = TextReRank.call(
            model=self._settings.rerank_model_name,
            query=query,
            documents=documents,
            top_n=min(top_k, len(documents)),
            return_documents=False,
        )
        status_code = response.get("status_code") if isinstance(response, dict) else getattr(response, "status_code", None)
        if status_code != 200:
            code = response.get("code", "unknown") if isinstance(response, dict) else getattr(response, "code", "unknown")
            message = (
                response.get("message", "unknown")
                if isinstance(response, dict)
                else getattr(response, "message", "unknown")
            )
            raise RuntimeError(f"DashScope rerank failed: {code} - {message}")
        output = response.get("output") if isinstance(response, dict) else getattr(response, "output", None)
        results = output.get("results") if isinstance(output, dict) else getattr(output, "results", None)
        results = results or []
        reranked: list[RetrievalChunk] = []
        for item in results:
            index_value = item.get("index", -1) if isinstance(item, dict) else getattr(item, "index", -1)
            index = int(index_value)
            if index < 0 or index >= len(initial):
                continue
            source_chunk = initial[index]
            score_value = (
                item.get("relevance_score", 0.0)
                if isinstance(item, dict)
                else getattr(item, "relevance_score", 0.0)
            )
            score = float(score_value)
            reranked.append(
                RetrievalChunk(
                    chunk_id=source_chunk.chunk_id,
                    title=source_chunk.title,
                    source=source_chunk.source,
                    score=round(score, 4),
                    content=source_chunk.content,
                    channel="rerank",
                    hit_mode=f"rerank(来自 {source_chunk.hit_mode})",
                )
            )
        return reranked

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
        hybrid_rrf_sorted = self._build_hybrid_rrf(all_chunks)

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
            for item in hybrid_rrf_sorted[:top_n]:
                dominant_channel = str(item["dominant_channel"])
                initial.append(
                    RetrievalChunk(
                        chunk_id=str(item["chunk_id"]),
                        title=str(item["title"]),
                        source=str(item["source"]),
                        score=float(item["fused_score"]),
                        content=str(item["content"]),
                        channel=dominant_channel,  # For UI channel badge compatibility.
                        hit_mode=f"hybrid_rrf({dominant_channel})",
                    )
                )

        if mode == "hybrid_rerank":
            final = self._rerank_with_dashscope(query=query, initial=initial, top_k=top_k)
        else:
            final = initial[:top_k]

        # Keep response order stable: highest relevance first.
        initial = sorted(initial, key=lambda item: item.score, reverse=True)
        final = sorted(final, key=lambda item: item.score, reverse=True)
        return initial, final, all_chunks


retrieval_service = RetrievalService()
