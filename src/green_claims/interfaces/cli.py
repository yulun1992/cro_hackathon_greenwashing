"""Command-line adapter for reproducible fixtures and explicitly selected live runs."""
import argparse
import json
from pathlib import Path
from green_claims.config import Settings
from green_claims.demo.fixtures import load_cases, demo_regulation
from green_claims.ingestion.parsers import parse_document, MAX_FILE_BYTES
from green_claims.pipeline import run_review
from green_claims.reporting.html import render_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Green claims evidence screening")
    parser.add_argument("--case", choices=["A", "B", "C"], default="A")
    parser.add_argument("--claims", type=Path, help="UTF-8 text, one claim per line; requires --disclosure")
    parser.add_argument("--disclosure", type=Path, help="UTF-8 supporting disclosure")
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--verification", choices=["none", "facts", "facts_and_judge"], default="none",
                        help="Optional live fact extraction and second-pass judge; adds 1 or 2 model calls")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--regulation", type=Path, help="PDF/TXT/MD replacing the fictional standard")
    sources.add_argument("--no-regulation", action="store_true")
    parser.add_argument("--version", default="Not specified")
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args(argv)
    if bool(args.claims) != bool(args.disclosure):
        parser.error("--claims and --disclosure must be supplied together")
    try:
        case = next(c for c in load_cases() if c["id"] == args.case)
        claims = args.claims.read_text(encoding="utf-8-sig") if args.claims else "\n".join(case["claims"])
        disclosure = args.disclosure.read_text(encoding="utf-8-sig") if args.disclosure else case["disclosure"]
        if args.regulation:
            if args.regulation.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("Regulation must be at most 10 MB.")
            regulation = parse_document(args.regulation.name, args.regulation.read_bytes(), args.version)
        else:
            regulation = None if args.no_regulation else demo_regulation()
        settings = Settings.from_env()
        mode = "Live AI" if args.mode == "live" else "Offline demo"
        client = settings.make_client() if args.mode == "live" else None
        report = run_review(claims, disclosure, regulation, mode, generator=client,
                            model=settings.model, language=settings.language, verification=args.verification)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.output_dir / "review.html").write_text(render_report(report), encoding="utf-8")
        print(json.dumps(report["summary"]))
        print(f"Saved review.json and review.html in {args.output_dir}")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Review failed: {exc}\n")
    return 0
