"""Full context for short documents; lexical budget selection for long ones."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from green_claims.models import Document, Passage
from green_claims.text import tokens

def select_passages(doc: Document | None, claims: list[dict], budget: int = 30_000) -> list[Passage]:
    """Full text for short files; transparent lexical shortlist for long files."""
    if not doc:
        return []
    if sum(len(p.text) for p in doc.passages) <= budget:
        return doc.passages
    query = tokens(" ".join(c["text"] for c in claims))
    query |= tokens("environmental evidence substantiation scope baseline emissions intensity target future packaging renewable misleading qualification applicability definitions")
    scored = sorted(enumerate(doc.passages), key=lambda pair: (-len(tokens(pair[1].text) & query), pair[0]))
    selected, used = [], 0
    for index, passage in scored:
        if used + len(passage.text) <= budget:
            selected.append((index, passage))
            used += len(passage.text)
    return [p for _, p in sorted(selected)]


class Retriever(Protocol):
    def retrieve(self, document: Document | None, claims: list[dict]) -> list[Passage]: ...

@dataclass(frozen=True)
class LexicalRetriever:
    budget: int = 30_000

    def __post_init__(self):
        if self.budget <= 0:
            raise ValueError("Retrieval character budget must be positive.")

    def retrieve(self, document: Document | None, claims: list[dict]) -> list[Passage]:
        return select_passages(document, claims, self.budget)
