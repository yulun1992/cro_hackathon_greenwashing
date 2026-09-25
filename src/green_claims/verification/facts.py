"""Fact alignment and bounded Decimal arithmetic, never a truth or compliance verdict."""
from decimal import Decimal, InvalidOperation
import re

from green_claims.models import Passage
from green_claims.text import normalize
from green_claims.validation.citations import verify_reference

DIMENSIONS = ("metric", "unit", "period", "baseline_period", "scope", "metric_basis", "nature")
UNKNOWN = {"", "unknown", "unspecified", "not specified", "not stated", "n/a", "none", "null"}
NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
PERCENT_TOLERANCE = Decimal("0.1")  # percentage points, never a confidence probability


def keyed_rows(raw, field, claims):
    rows = raw.get(field) if isinstance(raw, dict) else None
    if not isinstance(rows, list) or len(rows) != len(claims):
        raise ValueError(f"Expected exactly one {field} entry per claim.")
    if any(not isinstance(row, dict) or not isinstance(row.get("claim_id"), str) for row in rows):
        raise ValueError(f"Malformed {field} entries.")
    ids = [row["claim_id"] for row in rows]
    if len(set(ids)) != len(ids) or set(ids) != {c["id"] for c in claims}:
        raise ValueError(f"Missing, duplicate or unknown claim in {field}.")
    return {row["claim_id"]: row for row in rows}


def references(raw, sources, maximum=4):
    if not isinstance(raw, list) or len(raw) > maximum:
        return [], True
    checked = [verify_reference(ref, sources) for ref in raw]
    return [ref for ref in checked if ref], any(ref is None for ref in checked)


def read_number(raw, sources):
    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
        raise ValueError("An explicit source numeral is required.")
    text = raw["text"]
    if len(text) > 40 or not re.fullmatch(NUMBER, text):
        raise ValueError("Only unambiguous English-format numeric literals are supported.")
    ref = verify_reference(raw.get("reference"), sources)
    if not ref or not re.search(r"(?<![\w.,+\-])" + re.escape(text) + r"(?![\w.,])", ref["quote"]):
        raise ValueError("A number or its quotation is not present verbatim in the source.")
    # Do not silently treat a scaled/ranged/approximate literal as an exact value.
    nearby = re.escape(text)
    if re.search(nearby + r"\s*(?:million|billion|thousand|[–—-]|\bto\b)", ref["quote"], re.I):
        raise ValueError("Scaled or ranged values need explicit human normalization.")
    if re.search(r"\b(?:about|approximately|roughly|at least|at most|over|under|more than|less than|up to)\s*" + nearby, ref["quote"], re.I):
        raise ValueError("Approximate or bounded values are not exact comparison inputs.")
    value = Decimal(text.replace(",", ""))
    if not value.is_finite():
        raise ValueError("Numeric values must be finite.")
    return value, {"text": text, "reference": ref}


def read_fact(raw, sources):
    if raw is None:
        return None, False
    if not isinstance(raw, dict):
        return None, True
    values = {}
    for key in DIMENSIONS:
        value = raw.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > 300):
            return None, True
        values[key] = value.strip() if isinstance(value, str) else None
    refs, rejected = references(raw.get("references", []), sources)
    if not refs:
        rejected = True
    quantity = raw.get("quantity")
    if quantity is not None and not isinstance(quantity, dict):
        return None, True
    return {**values, "references": refs, "quantity": quantity,
            "quote_verified": bool(refs) and not rejected, "extraction_semantics_verified": False}, rejected


def known(value):
    return isinstance(value, str) and normalize(value).lower() not in UNKNOWN


def literal_premises_present(fact):
    """Conservatively require units and date labels in each side's quoted source."""
    if not fact:
        return False
    cited = " ".join(ref["quote"] for ref in fact["references"]).casefold()
    for field in ("unit", "period", "baseline_period"):
        label = fact.get(field)
        if known(label) and normalize(label).casefold() not in normalize(cited).casefold():
            return False
    return True


def signed_change(raw, sources, kind):
    magnitude, checked = read_number(raw.get("value"), sources)
    if magnitude < 0:
        raise ValueError("Use a nonnegative percentage magnitude plus an explicit direction.")
    direction = raw.get("direction")
    words = {"increase": r"(?:increas\w*|rose|rise|grew|growth)",
             "decrease": r"(?:decreas\w*|fell|fall|reduc\w*|declin\w*|drop\w*)"}
    if direction not in words:
        raise ValueError("An explicit increase/decrease direction is required.")
    phrase = checked["reference"]["quote"]
    token = re.escape(checked["text"])
    unit_pattern = r"\s*(?:%|percent\b)" if kind == "relative_change_pct" else r"\s*(?:percentage points?\b)"
    numeric_expression = token + unit_pattern
    if not re.search(numeric_expression, phrase, re.I):
        raise ValueError("The claimed change unit must be explicit next to the numeral.")
    other = "decrease" if direction == "increase" else "increase"
    # The direction and magnitude must occur together; ambiguous mixed directions are skipped.
    if re.search(words[other], phrase, re.I) or re.search(r"\b(?:not|never|no)\b", phrase, re.I):
        raise ValueError("The direction is negated or ambiguous in the quoted statement.")
    if not re.search(r"\b" + words[direction] + r"\b[^.;!?\n]{0,100}?" + numeric_expression +
                     r"|" + numeric_expression + r"\s+(?:" + words[direction] + r")\b", phrase, re.I):
        raise ValueError("Cannot independently align the change direction with its numeral.")
    return magnitude * (-1 if direction == "decrease" else 1), checked


def compute_quantity(claim, disclosure, claim_sources, disclosure_sources):
    cq, dq = claim.get("quantity"), disclosure.get("quantity")
    if not cq or not dq:
        return {"status": "not_computed", "reason": "No explicit supported numeric comparison was extracted."}
    if not isinstance(cq, dict) or not isinstance(dq, dict):
        return {"status": "not_computed", "reason": "Malformed quantity data."}
    kind = cq.get("kind")
    if not isinstance(kind, str) or kind not in {"level", "relative_change_pct", "percentage_point_change"} or dq.get("kind") != kind:
        return {"status": "not_computed", "reason": "The quantity kinds are missing, different or unsupported."}
    try:
        if kind == "level":
            expected, checked_claim = read_number(cq.get("value"), claim_sources)
            actual, checked_value = read_number(dq.get("value"), disclosure_sources)
            operands = {"claim": checked_claim, "disclosure": checked_value}
            formula = "disclosure value - claimed value"
            tolerance = Decimal("0")
            if claim["unit"] == "%":
                for checked in (checked_claim, checked_value):
                    if not re.search(re.escape(checked["text"]) + r"\s*(?:%|percent\b)", checked["reference"]["quote"], re.I):
                        raise ValueError("Percentage level must have an explicit percent marker.")
        else:
            if not known(claim.get("baseline_period")) or not known(disclosure.get("baseline_period")):
                raise ValueError("A baseline period is required for change calculations.")
            expected, checked_claim = signed_change(cq, claim_sources, kind)
            baseline, checked_baseline = read_number(dq.get("baseline"), disclosure_sources)
            current, checked_current = read_number(dq.get("current"), disclosure_sources)
            if baseline <= 0:
                raise ValueError("A positive baseline is required for this bounded checker.")
            # Temporal association is still model-extracted, but reject absent or mixed date labels.
            for period, checked in [(disclosure["baseline_period"], checked_baseline), (disclosure["period"], checked_current)]:
                if normalize(period) not in normalize(checked["reference"]["quote"]):
                    raise ValueError("Each operand quotation must explicitly include its extracted period.")
            if kind == "relative_change_pct":
                actual = (current / baseline - 1) * 100
                formula = "(current / baseline - 1) * 100"
            else:
                if normalize(disclosure["unit"]) != "%":
                    raise ValueError("Percentage-point comparisons require percent-valued operands.")
                for value, checked in [(baseline, checked_baseline), (current, checked_current)]:
                    if not re.search(re.escape(checked["text"]) + r"\s*(?:%|percent\b)", checked["reference"]["quote"], re.I):
                        raise ValueError("Each percentage operand must have an explicit percent marker.")
                actual = current - baseline
                formula = "current percentage - baseline percentage"
            tolerance = PERCENT_TOLERANCE
            operands = {"claim": checked_claim, "baseline": checked_baseline, "current": checked_current}
        difference = actual - expected
        return {"status": "match" if abs(difference) <= tolerance else "mismatch",
                "kind": kind, "claimed_value": str(expected), "calculated_value": str(actual),
                "difference": str(difference), "absolute_tolerance": str(tolerance),
                "formula": formula, "operands": operands,
                "premises": "Conditional on model-extracted metric, units, scope and temporal associations; not a full claim verdict."}
    except (ValueError, InvalidOperation, ArithmeticError, TypeError) as exc:
        return {"status": "not_computed", "reason": str(exc)}


def check_facts(raw, context):
    rows = keyed_rows(raw, "pairs", context["claims"])
    disclosure_sources = {p.id: p for p in context["disclosure"]}
    results = []
    for claim in context["claims"]:
        row = rows[claim["id"]]
        claim_sources = {claim["id"]: Passage(claim["id"], claim["text"], "Original claim")}
        cf, bad_claim = read_fact(row.get("claim_fact"), claim_sources)
        df, bad_disclosure = read_fact(row.get("disclosure_fact"), disclosure_sources)
        note = row.get("note", "")
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError("Invalid extraction note.")
        dimensions = []
        for name in DIMENSIONS:
            a, b = (cf or {}).get(name), (df or {}).get(name)
            status = "unknown" if not known(a) or not known(b) else "aligned" if normalize(a).casefold() == normalize(b).casefold() else "different"
            dimensions.append({"dimension": name, "claim": a, "disclosure": b, "status": status})
        required = [d for d in dimensions if d["dimension"] != "baseline_period"]
        if bad_claim or bad_disclosure or not literal_premises_present(cf) or not literal_premises_present(df):
            alignment = "unverified"
        elif any(d["status"] == "different" for d in dimensions):
            alignment = "not_aligned"
        elif cf is None or df is None or any(d["status"] == "unknown" for d in required):
            alignment = "incomplete"
        else:
            alignment = "aligned"
        arithmetic = compute_quantity(cf, df, claim_sources, disclosure_sources) if alignment == "aligned" else {
            "status": "not_computed", "reason": "Required dimensions are missing, different or not backed by valid quotations."}
        # Do not retain unvalidated model quantities as verified output. Only checked operands are displayed.
        for fact in [cf, df]:
            if fact is not None:
                fact.pop("quantity", None)
        results.append({"claim_id": claim["id"], "status": alignment, "dimensions": dimensions,
                        "claim_fact": cf, "disclosure_fact": df, "arithmetic": arithmetic,
                        "note": note, "semantic_extraction_verified": False})
    return results
