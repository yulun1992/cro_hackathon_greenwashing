"""Application service shared by CLI, notebook and future API entry points."""
from green_claims.models import Document, ReviewContext
from green_claims.ingestion.chunking import split_text
from green_claims.retrieval.lexical import Retriever, LexicalRetriever
from green_claims.generation.client import Generator
from green_claims.demo.fixtures import demo_analysis
from green_claims.validation.findings import validate_findings
from green_claims.reporting.reports import make_report, fingerprint

def parse_claims(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 15:
        raise ValueError("Enter 1–15 claims, one claim per line.")
    if any(len(line) > 2000 for line in lines):
        raise ValueError("Keep each claim under 2,000 characters.")
    return [{"id": f"C{i}", "text": line} for i, line in enumerate(lines, 1)]


def prepare(claims_text: str, disclosure_text: str, regulation: Document | None, retriever: Retriever | None = None) -> ReviewContext:
    claims = parse_claims(claims_text)
    if not disclosure_text.strip():
        raise ValueError("Add supporting disclosure text before comparing.")
    if len(disclosure_text) > 35_000:
        raise ValueError("For this MVP, keep the disclosure under 35,000 characters.")
    disclosure = split_text(disclosure_text, "D")
    selected = (retriever or LexicalRetriever()).retrieve(regulation, claims)
    return {"claims": claims, "disclosure": disclosure, "regulation": regulation,
            "selected_regulation": selected}


def run_review(claims_text: str, disclosure_text: str, regulation: Document | None = None,
               mode: str = "Offline demo", *, generator: Generator | None = None,
               retriever: Retriever | None = None, model: str = "", language: str = "English") -> dict:
    if mode not in {"Offline demo", "Live AI"}:
        raise ValueError("Mode must be Offline demo or Live AI.")
    context = prepare(claims_text, disclosure_text, regulation, retriever)
    if mode == "Offline demo":
        findings, warnings = demo_analysis(context)
    else:
        if generator is None:
            raise ValueError("Live AI requires a configured generator.")
        findings, warnings = validate_findings(generator.generate(context, language), context)
    if regulation and len(context["selected_regulation"]) < len(regulation.passages):
        warnings.append("Long regulation: only a keyword shortlist was sent to the model. Relevant provisions may be missed.")
    report = make_report(context, findings, warnings, mode, model)
    report["input_fingerprint"] = fingerprint(claims_text, disclosure_text, regulation, mode, model)
    return report
