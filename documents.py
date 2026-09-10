"""Small, local document parser. Citations address the extracted text, not a vector DB."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 500_000
MAX_PDF_PAGES = 250


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


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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


def parse_document(filename: str, content: bytes, version: str = "Not specified") -> Document:
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("Upload a non-empty file of at most 10 MB.")
    suffix = Path(filename).suffix.lower()
    warnings = []
    passages = []
    total_chars = 0
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF support needs pypdf. Install it in Databricks, or upload UTF-8 TXT/MD.") from exc
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("The PDF is password-protected. Upload an unlocked copy.")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError("This MVP accepts PDFs up to 250 pages. Upload the relevant section.")
            for page_number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                total_chars += len(text)
                if total_chars > MAX_TEXT_CHARS:
                    raise ValueError("Extracted text exceeds 500,000 characters. Upload a shorter document.")
                if not text.strip():
                    warnings.append(f"PDF page {page_number}: no extractable text; OCR may be needed.")
                    continue
                for item in split_text(text, "temp"):
                    passages.append(Passage(f"R{len(passages) + 1:04d}", item.text,
                                            f"PDF page {page_number}, {item.location}"))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Cannot read this PDF. Try an unlocked text PDF or UTF-8 TXT/MD.") from exc
    elif suffix in {".txt", ".md"}:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Save the text file as UTF-8 and upload it again.") from exc
        if len(text) > MAX_TEXT_CHARS:
            raise ValueError("Text exceeds 500,000 characters. Upload a shorter document.")
        passages = split_text(text, "R")
    else:
        raise ValueError("Supported regulation formats: PDF, TXT and MD.")
    if not passages:
        raise ValueError("No readable text found. Scanned PDFs need OCR before upload.")
    return Document(Path(filename).name, version.strip() or "Not specified",
                    sha256(content).hexdigest(), passages, warnings)


STOP_WORDS = set("the a an and or of to in for by our we all is are was were be with from on as at this that shall must should company claim claims".split())


def tokens(text: str) -> set[str]:
    english = set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    return english | set("".join(chinese[i:i+2]) for i in range(len(chinese)-1))


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


def verify_reference(reference: dict, source: dict[str, Passage]) -> dict | None:
    if not isinstance(reference, dict):
        return None
    if not isinstance(reference.get("id"), str):
        return None
    passage = source.get(reference.get("id"))
    quote = reference.get("quote", "")
    if not passage or not isinstance(quote, str) or len(normalize(quote)) < 12:
        return None
    if normalize(quote) not in normalize(passage.text):
        return None
    # Return the locator from our parser, never one generated by the model.
    return {"id": passage.id, "quote": quote, "location": passage.location,
            "quote_verified": True}


def passage_dicts(passages: list[Passage]) -> list[dict]:
    return [asdict(p) for p in passages]
