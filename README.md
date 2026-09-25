# Green Claims RAG

A modular Python application for comparing environmental claims with supplied disclosure and screening them against supplied regulation. The original hackathon demo is preserved in [`mvp_demo/`](mvp_demo/).

**This refactor preserves the existing method and results.** It separates ingestion, retrieval, generation, validation and presentation. Retrieval is still the original lexical baseline; embeddings, a vector database, multiple regulations and effective-date verification are not implemented yet.

## Web interface

An independent React frontend now connects to the existing pipeline through FastAPI. It supports editable claims/disclosure, regulation upload, Offline demo / Live AI, result filters, full source-passage inspection and JSON export.

Live AI can add [structured fact alignment, conditional arithmetic and a second-pass LLM judge](docs/FACT_VERIFICATION.md). The original finding and the judge opinion remain distinct; conflicting or incomplete checks are flagged for human review.

```bash
python -m pip install -e '.[web,pdf]'
npm ci --prefix frontend
npm run build --prefix frontend
green-claims-web
```

Open `http://127.0.0.1:8000` on the machine running the server. Live AI requires server-side model configuration. This is a local application; it has not been publicly deployed. See [web setup and testing](docs/WEB_APP.md).

## Choose an entry point

| Purpose | Entry point |
| --- | --- |
| Original one-file Databricks demo, unchanged | [`mvp_demo/Green_Claims_Databricks.ipynb`](mvp_demo/Green_Claims_Databricks.ipynb) |
| New modular Databricks notebook, with optional upload UI | [`notebooks/Green_Claims_RAG.ipynb`](notebooks/Green_Claims_RAG.ipynb) |
| Independent web workspace | `green-claims-web` — see [setup](docs/WEB_APP.md) |
| Local command line | `python -m green_claims` or `green-claims` after installation |
| Python application integration | `green_claims.pipeline.run_review()` |
| Original business context and methodology | [`mvp_demo/BUSINESS_AND_METHODOLOGY_SUMMARY.md`](mvp_demo/BUSINESS_AND_METHODOLOGY_SUMMARY.md) |

The archived notebook remains self-contained. The new notebook needs the **whole repository** in a Databricks Git folder, or an installed package. It imports the package instead of embedding copies of source code. Set `REPO_ROOT` in its first cell if the repository cannot be found automatically. Its fallback review runs without widgets; set `SHOW_UI = True` for the interactive view. Rerun the view cell after changing settings.

## Run locally

Python 3.10 or newer:

```bash
python -m pip install -e .
python -m green_claims --case A --output-dir reports/case-a
python -m green_claims --case B --output-dir reports/case-b
python -m green_claims --case C --output-dir reports/case-c
```

Each command writes `review.json` and `review.html`. Default mode is **Offline demo**, replaying authored examples; it does not call AI or assess regulation. Edited input requires Live AI.

Optional support:

```bash
python -m pip install -e '.[pdf,notebook]'
```

For a source-only run without installing the package:

```bash
PYTHONPATH=src python -m green_claims --case A
```

## Live AI and your regulation

Configure `AZURE_OPENAI_CHAT_URL` (full chat/completions URL), `AZURE_OPENAI_DEPLOYMENT` (deployment name) and `AZURE_OPENAI_API_KEY` using your approved environment/secret setup. `.env.example` is a reference and is **not loaded automatically**. Never commit actual credentials. Optional variables are `AZURE_OPENAI_AUTH_TYPE` (`api-key` or `bearer`) and `OUTPUT_LANGUAGE`.

```bash
python -m green_claims --mode live --case A \
  --regulation /path/to/regulation.pdf --version 'reviewed-version-label' \
  --verification facts_and_judge \
  --output-dir reports/live
```

Custom materials:

```bash
python -m green_claims --mode live \
  --claims /path/to/claims.txt --disclosure /path/to/disclosure.txt \
  --regulation /path/to/regulation.md --version 'reviewed-version-label'
```

`--regulation` replaces the fictional standard. `--no-regulation` removes it. Claims and disclosure are UTF-8 text. PDF support is only needed for a PDF regulation. A version label is user-supplied metadata, not proof of currency or applicability.

In Databricks, fill `Settings(secret_scope=..., secret_key=...)` with **secret names**, and pass `dbutils` to `settings.make_client(dbutils)`. Secrets are read only for Live AI. The HTTP adapter supports API keys or an existing bearer token; it does not obtain or refresh Entra tokens. Approved company clients can implement the `Generator` interface.

## Structure

| Path | Responsibility |
| --- | --- |
| `mvp_demo/` | Byte-for-byte archive of all 26 original tracked files |
| `src/green_claims/models.py` | Shared `Document`, `Passage`, claim/context contracts |
| `src/green_claims/ingestion/` | PDF/TXT/MD extraction, paragraph and character chunking |
| `src/green_claims/retrieval/` | Retriever interface and lexical context selection |
| `src/green_claims/generation/` | Context serialization, preserved prompt, model transport |
| `src/green_claims/validation/` | Output structure and source quotation checks |
| `src/green_claims/verification/` | Optional fact extraction, conditional Decimal arithmetic and judge opinion |
| `src/green_claims/reporting/` | Report schema, fingerprint and escaped HTML |
| `src/green_claims/demo/` | Explicit fixture replay, packaged synthetic data and arithmetic |
| `src/green_claims/pipeline.py` | One orchestration service for every entry point |
| `src/green_claims/interfaces/` | CLI and optional notebook widgets |
| `frontend/` | React + TypeScript interface and interaction tests |
| `src/green_claims/interfaces/api.py` | FastAPI adapter and local web launcher |
| `notebooks/` | Thin Databricks entry point |
| `tests/` | Behavioral tests and comparisons against the archived MVP |
| `docs/` | Architecture, migration, validation and proposed next feature |

## Verify

```bash
python -m unittest discover -s tests -v
```

Tests compare complete offline reports excluding timestamps, original prompt messages, and long-document chunk/retrieval output against the archived implementation. They also cover a simulated HTTP endpoint, citation rejection, source replacement, PDF extraction, the old and new notebooks, all three CLI cases and injected model/retriever behavior. These are software regression checks, not measurements of live model accuracy.

The original suite can still be run separately:

```bash
cd mvp_demo
python -m unittest discover -s tests -v
```

See [architecture and migration](docs/ARCHITECTURE.md), [fact verification and regulation's role](docs/FACT_VERIFICATION.md), [validation results](docs/VALIDATION.md), and [multiple regulations and temporal validity proposal](docs/NEXT_FEATURE_MULTI_REGULATION.md).
