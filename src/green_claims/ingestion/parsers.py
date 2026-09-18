"""Extract UTF-8 text or PDF pages, preserving the original MVP limits."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from green_claims.models import Document, Passage
from green_claims.ingestion.chunking import split_text

MAX_FILE_BYTES = 10 * 1024 * 1024


MAX_TEXT_CHARS = 500_000


MAX_PDF_PAGES = 250


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
