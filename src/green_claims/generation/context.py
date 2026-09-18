"""Serialize only the selected evidence, with the original prompt contract."""
from dataclasses import asdict
from green_claims.generation.prompts import SYSTEM_PROMPT

def build_messages(context: dict, language: str = "English") -> list[dict]:
    import json
    payload = {
        "output_language": language,
        "claims": context["claims"],
        "disclosure_passages": [asdict(p) for p in context["disclosure"]],
        "regulation_metadata": context["regulation"].metadata() if context["regulation"] else None,
        "regulation_passages": [asdict(p) for p in context["selected_regulation"]],
    }
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
