"""Small deterministic BM25 implementation with no runtime dependencies."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokenize(value: str) -> tuple[str, ...]:
    """Normalize identifiers, punctuation, and camelCase into lexical terms."""
    if not isinstance(value, str):
        raise TypeError("BM25 text must be a string")
    expanded = _CAMEL_RE.sub(" ", value)
    return tuple(token.casefold() for token in _TOKEN_RE.findall(expanded))


@dataclass(frozen=True)
class SearchDocument:
    id: str
    text: str
    payload: Any = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("search document id must not be empty")
        if not isinstance(self.text, str):
            raise TypeError("search document text must be a string")


@dataclass(frozen=True)
class ScoredDocument:
    document: SearchDocument
    score: float


class BM25Index:
    """Immutable Okapi BM25 index with deterministic tie-breaking."""

    def __init__(
        self,
        documents: Iterable[SearchDocument],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        if not 0 < k1 <= 5:
            raise ValueError("k1 must be greater than 0 and at most 5")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        ordered = tuple(sorted(documents, key=lambda item: item.id))
        ids = [document.id for document in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("search document ids must be unique")
        self.documents = ordered
        self.k1 = k1
        self.b = b
        self._frequencies = tuple(
            Counter(tokenize(document.text)) for document in ordered
        )
        self._lengths = tuple(sum(row.values()) for row in self._frequencies)
        self._average_length = (
            sum(self._lengths) / len(self._lengths)
            if self._lengths
            else 0.0
        )
        document_frequency: Counter[str] = Counter()
        for row in self._frequencies:
            document_frequency.update(row.keys())
        count = len(ordered)
        self._idf = {
            term: math.log(
                1.0 + (count - frequency + 0.5) / (frequency + 0.5)
            )
            for term, frequency in document_frequency.items()
        }

    def search(self, query: str, *, limit: int = 10) -> tuple[ScoredDocument, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("BM25 result limit must be between 1 and 100")
        terms = Counter(tokenize(query))
        if not terms or not self.documents:
            return ()
        results: list[ScoredDocument] = []
        for document, frequencies, length in zip(
            self.documents,
            self._frequencies,
            self._lengths,
            strict=True,
        ):
            score = 0.0
            length_ratio = (
                length / self._average_length
                if self._average_length
                else 0.0
            )
            for term, query_frequency in terms.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * length_ratio
                )
                score += (
                    self._idf.get(term, 0.0)
                    * (frequency * (self.k1 + 1.0) / denominator)
                    * query_frequency
                )
            if score > 0:
                results.append(ScoredDocument(document=document, score=score))
        results.sort(key=lambda item: (-item.score, item.document.id))
        return tuple(results[:limit])
