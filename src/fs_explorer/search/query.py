"""
Indexed query helpers for agent tools.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..storage import DuckDBStorage


@dataclass(frozen=True)
class SearchHit:
    """Ranked chunk hit from indexed search."""

    doc_id: str
    relative_path: str
    absolute_path: str
    position: int
    text: str
    score: int


class IndexedQueryEngine:
    """Thin wrapper around storage-level chunk search."""

    def __init__(self, storage: DuckDBStorage) -> None:
        self.storage = storage

    def search(self, *, corpus_id: str, query: str, limit: int = 5) -> list[SearchHit]:
        rows = self.storage.search_chunks(corpus_id=corpus_id, query=query, limit=limit)
        return [
            SearchHit(
                doc_id=row["doc_id"],
                relative_path=row["relative_path"],
                absolute_path=row["absolute_path"],
                position=row["position"],
                text=row["text"],
                score=row["score"],
            )
            for row in rows
        ]
