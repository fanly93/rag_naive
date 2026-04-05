import hashlib
from typing import List

import dashscope
from dashscope import TextEmbedding
from llama_index.core.embeddings import BaseEmbedding
from pydantic import Field

from app.core.config import get_settings


class DeterministicEmbedding(BaseEmbedding):
    model_name: str = "deterministic-hash-embedding"
    dimension: int = Field(default=256, ge=8, le=4096)

    def _hash_to_vector(self, text: str) -> List[float]:
        if not text:
            text = " "
        output: List[float] = []
        salt = 0
        while len(output) < self.dimension:
            digest = hashlib.sha256(f"{salt}:{text}".encode("utf-8")).digest()
            for value in digest:
                output.append((value / 127.5) - 1.0)
                if len(output) >= self.dimension:
                    break
            salt += 1
        return output

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._hash_to_vector(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._hash_to_vector(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vector(item) for item in texts]


class DashScopeEmbedding(BaseEmbedding):
    model_name: str = Field(default="text-embedding-v4")
    api_key: str = Field(default="")
    dimension: int = Field(default=1024, ge=8, le=4096)

    def _ensure_api_key(self) -> None:
        if not self.api_key:
            raise ValueError("DashScope API key is required for real embedding.")
        dashscope.api_key = self.api_key

    def _call(self, texts: List[str], text_type: str) -> List[List[float]]:
        self._ensure_api_key()
        response = TextEmbedding.call(model=self.model_name, input=texts, text_type=text_type)
        status_code = response.get("status_code") if isinstance(response, dict) else getattr(response, "status_code", None)
        if status_code != 200:
            code = response.get("code", "unknown") if isinstance(response, dict) else getattr(response, "code", "unknown")
            message = (
                response.get("message", "unknown")
                if isinstance(response, dict)
                else getattr(response, "message", "unknown")
            )
            raise RuntimeError(f"DashScope embedding failed: {code} - {message}")
        output = response.get("output") if isinstance(response, dict) else getattr(response, "output", None)
        raw_embeddings = output.get("embeddings") if isinstance(output, dict) else getattr(output, "embeddings", None)
        raw_embeddings = raw_embeddings or []
        vectors: List[List[float]] = []
        for item in raw_embeddings:
            vector_values = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", [])
            vector = [float(value) for value in (vector_values or [])]
            if not vector:
                raise RuntimeError("DashScope embedding vector is empty.")
            vectors.append(vector)
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"DashScope embedding count mismatch: expect {len(texts)}, got {len(vectors)}"
            )
        return vectors

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._call([query], text_type="query")[0]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._call([text], text_type="document")[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._call(texts, text_type="document")


def create_embedding_model() -> BaseEmbedding:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise ValueError("DashScope API key is required for real embedding.")
    return DashScopeEmbedding(
        model_name=settings.embedding_model_name,
        api_key=settings.dashscope_api_key,
        dimension=settings.embedding_dim,
    )
