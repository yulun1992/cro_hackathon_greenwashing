# Refactor validation

Validated on 2026-09-18 against original commit `0562f75366bb733b337e8c5eae4f1bcb1e93f1ca`.

| Check | Result |
| --- | --- |
| Archive fidelity | All 26 original tracked files match `mvp_demo/` byte for byte |
| New test suite with optional widget support | 24 passed, no skips |
| New test suite without widget support | 23 passed; 1 optional widget test skipped |
| Existing behavior | All 15 original behavior tests retained with package imports |
| Offline report parity | All three complete reports match the archived engine, excluding only generation timestamps |
| Model input parity | System prompt and serialized user messages match the archived client for all three cases |
| Long-document parity | Chunk texts/IDs/locations and the selected lexical shortlist match the archived parser/retriever |
| CLI | Cases A, B and C produce matching JSON and HTML exports |
| Notebooks | Archived self-contained notebook and new modular fallback execute successfully |
| Widget callbacks | Compare, switch case, invalidate old output and recover from missing upload checked with real ipywidgets |
| Upload adapter | ipywidgets 7-style and 8-style upload payloads resolve the new source |
| Model transport | Local simulated Chat Completions endpoint checks request and citation processing |
| Packaging | Wheel builds; installed package runs Case C outside the repository and loads bundled demo resources |

The original fixture outcomes remain: A has three contradicted claims; B has two insufficient-evidence claims and one not-comparable claim; C has three supported claims. Offline regulatory conclusions remain `not_assessed`.

## Reproduce

```bash
python -m pip install -e '.[pdf,notebook]'
python -m unittest discover -s tests -v
```

The PDF and widget checks require their optional dependencies. The core package has no third-party runtime dependency.

## Limits

No company Azure endpoint, company credentials or live model output was used. Request parity does not guarantee identical stochastic model answers. Actual Databricks browser rendering, permissions and network access still need a check in the company environment. These tests do not measure regulatory completeness, semantic citation relevance or detection accuracy. Multi-regulation ingestion and temporal verification remain a proposal.

## Web interface follow-up — 2026-09-19

- Python suite: **34 passed, 1 optional ipywidgets test skipped** (widget dependency unavailable in this web-test environment).
- React interaction suite: **7 passed** using Testing Library and jsdom.
- TypeScript check and Vite production build: passed.
- The real local HTTP server served built frontend assets, returned synthetic cases and completed Case A with three contradicted findings.
- New API tests confirm all three reports match the existing pipeline apart from timestamps, including upload replacement and source inspection data. They also check Live AI validation/failure paths using a fake generator, safe credential errors, input/file limits and same-origin requests.
- UI tests cover result filters, full-source inspection, case changes, result invalidation, ignored late responses, upload/version fields, errors/retry, Live AI labeling and JSON download initiation.
- The managed browser could not open the local preview (`ERR_BLOCKED_BY_CLIENT`). Actual browser rendering, mobile layout, native file chooser/download behavior and live Azure connectivity are **not verified**. No public deployment was created.
