"""Parity baseline: blank-line paragraphs, 1,800 characters, no overlap."""
import re
from green_claims.models import Passage

def split_text(text: str, prefix: str, location: str = "paragraph") -> list[Passage]:
    """Preserve paragraph order and location; split long paragraphs at word boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    result = []
    for number, paragraph in enumerate(paragraphs, 1):
        chunks = []
        while len(paragraph) > 1800:
            boundary = paragraph.rfind(" ", 0, 1800)
            if boundary < 900:
                boundary = 1800
            chunks.append(paragraph[:boundary])
            paragraph = paragraph[boundary:].lstrip()
        if paragraph:
            chunks.append(paragraph)
        for part, chunk in enumerate(chunks, 1):
            result.append(Passage(f"{prefix}{len(result) + 1:04d}", chunk,
                                  f"{location} {number}" + (f", part {part}" if len(chunks) > 1 else "")))
    return result
