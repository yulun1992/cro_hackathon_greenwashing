"""Shared source contracts. Passage IDs remain local to one prepared context."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TypedDict

@dataclass(frozen=True)
class Passage:
    id: str
    text: str
    location: str


@dataclass
class Document:
    filename: str
    version: str
    sha256: str
    passages: list[Passage]
    warnings: list[str]

    def metadata(self):
        return {"filename": self.filename, "version": self.version,
                "sha256": self.sha256, "passage_count": len(self.passages),
                "latest_version_verified": False, "warnings": self.warnings}


class Claim(TypedDict):
    id: str
    text: str

class ReviewContext(TypedDict):
    claims: list[Claim]
    disclosure: list[Passage]
    regulation: Document | None
    selected_regulation: list[Passage]
