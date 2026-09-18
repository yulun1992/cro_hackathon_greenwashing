from datetime import datetime, timezone
from hashlib import sha256
import json
from green_claims.models import Document
from green_claims.demo.fixtures import numeric_checks
from green_claims.validation.findings import STATUSES

def fingerprint(claims_text: str, disclosure_text: str, regulation: Document | None, mode: str, model: str = "") -> str:
    return sha256(json.dumps([claims_text, disclosure_text, regulation.metadata() if regulation else None,
                             mode, model], sort_keys=True).encode()).hexdigest()


def make_report(context: dict, findings: list[dict], warnings: list[str], mode: str, model: str = "") -> dict:
    doc = context["regulation"]
    count = {s: sum(f["status"] == s for f in findings) for s in sorted(STATUSES)}
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": mode, "model": model if mode == "Live AI" else None,
            "summary": count, "findings": findings, "numeric_checks": numeric_checks(context),
            "warnings": warnings + (doc.warnings if doc else []),
            "regulation": doc.metadata() if doc else None,
            "regulation_passages_sent": len(context["selected_regulation"]),
            "regulation_total_passages": len(doc.passages) if doc else 0,
            "limitations": ["Screening signals require human review; no legal compliance determination.",
                            "Uploaded version and legal applicability are not independently verified.",
                            "Quote existence is checked; semantic relevance and reasoning are not independently verified.",
                            "Long regulations use a lexical shortlist, so relevant provisions may be missed."]}
