"""Optional reciprocal-rank fusion; lexical retrieval remains the default."""

from __future__ import annotations

from collections.abc import Iterable


def reciprocal_rank_fusion(
    rankings: Iterable[Iterable[str]],
    *,
    limit: int,
    rank_constant: int = 60,
) -> tuple[tuple[str, float], ...]:
    if not 1 <= limit <= 100:
        raise ValueError("fusion limit must be between 1 and 100")
    if rank_constant <= 0:
        raise ValueError("rank_constant must be positive")
    scores: dict[str, float] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, document_id in enumerate(ranking, start=1):
            if not document_id or document_id in seen:
                continue
            seen.add(document_id)
            scores[document_id] = scores.get(document_id, 0.0) + (
                1.0 / (rank_constant + rank)
            )
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return tuple(ordered[:limit])
