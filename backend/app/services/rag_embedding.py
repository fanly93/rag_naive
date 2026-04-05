import hashlib
from typing import List

from llama_index.core.embeddings import BaseEmbedding
from pydantic import Field


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
