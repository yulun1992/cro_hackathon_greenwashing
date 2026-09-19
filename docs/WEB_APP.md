# Web review workspace

The independent frontend uses React and TypeScript. FastAPI serves the built web assets and delegates analysis to the same `run_review()` pipeline used by the CLI and notebook. The original archived MVP is unchanged.

## Start the application

Prerequisites: Python 3.10+ and a Node.js version supported by the locked Vite release (Node 22 or 24 recommended). Run the following commands from the repository root:

```bash
python -m pip install -e '.[web,pdf]'
npm ci --prefix frontend
npm run build --prefix frontend
green-claims-web
```

Open `http://127.0.0.1:8000` in your own browser on that computer. If the console script is not on your PATH, use `python -m green_claims.interfaces.api` instead. The server binds to loopback by default. `--port 8001` changes the local port. If running outside the repository directory, pass `--static-dir /absolute/path/to/frontend/dist`.

The browser does not need Python. Python and Node are needed on the machine used to install/build this application; once built, the backend serves the compiled assets. This local web server is a separate entry point from Databricks Notebook. Starting it on a Databricks driver does not automatically publish a browser-accessible app.

## Review flow

1. Select synthetic case A, B or C, or choose Custom material.
2. Review/edit one environmental claim per line and the disclosure text.
3. Choose the fictional standard, upload one PDF/TXT/MD regulation, or select No regulation.
4. For an uploaded regulation, enter a version label. This does not verify its currency.
5. Choose Offline demo or Live AI, then click Compare & screen.
6. Filter by comparison status, expand regulatory assessments and click a source quotation to inspect its full extracted passage.
7. Export the original report JSON for an evidence record.

Offline demo accepts only the three unchanged examples and returns authored findings. Uploaded regulation can supply candidate passages, but offline mode does not assess regulation. Custom/edited material requires Live AI. Errors never fall back to authored results. Changing inputs clears the previous report and export; late responses are ignored so old results cannot appear under new inputs.

## Configure Live AI on the server

The browser never accepts or receives API keys. Before starting the backend, configure these using your approved server environment:

| Variable | Meaning |
| --- | --- |
| `AZURE_OPENAI_CHAT_URL` | Full approved Chat Completions endpoint, including required query parameters |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name |
| `AZURE_OPENAI_API_KEY` | API key or existing bearer credential, stored on the server only |
| `AZURE_OPENAI_AUTH_TYPE` | `api-key` by default, or `bearer` |
| `OUTPUT_LANGUAGE` | `English` by default |

`.env.example` is documentation only; the app does not automatically load `.env` files. Live AI becomes available in the UI when the server has an endpoint, deployment and credential configuration. This detects configuration presence, not successful model connectivity. A live request is still needed to verify the endpoint.

For a Databricks-specific hosting adapter, construct the app with `create_app(settings, dbutils=dbutils, static_dir=...)`. Plain local Python cannot resolve Databricks secrets by name. For another approved model authentication scheme, extend the server-side adapter; do not put it in frontend code.

## Development

Use two terminals from the repository root:

```bash
# Terminal 1
python -m green_claims.interfaces.api --api-only

# Terminal 2
npm run dev --prefix frontend
```

Use the Vite address printed in terminal 2. Vite proxies `/api` to the Python server on port 8000; it preserves the browser Host header so same-origin checks still work. Production-style local serving uses one FastAPI origin and needs no CORS configuration. Fonts and application assets are bundled locally; there is no runtime font CDN dependency.

## API contract

| Route | Response or input |
| --- | --- |
| `GET /api/config` | Live-mode configuration availability and input limits; no endpoints or credentials |
| `GET /api/cases` | Only synthetic IDs, names, claims and disclosure; no expected findings |
| `POST /api/reviews` | Multipart fields `claims`, `disclosure`, `mode`, `regulation_source`, `version`, optional `regulation_file` |

`mode` is exactly `Offline demo` or `Live AI`. `regulation_source` is `demo`, `upload`, or `none`. Uploaded files are required for `upload` and rejected for other source selections, preventing silent source mismatches.

Successful responses contain `{report, sources}`. `report` retains the existing pipeline schema and fingerprint. `sources` contains the disclosure passages and selected regulation passages actually available to the model, for the source inspector. Report conclusions are not inferred by frontend JavaScript.

The adapter prepares an inspection context and runs the deterministic baseline pipeline with the same inputs. If future retrieval becomes nondeterministic or stateful, return the actual run context from the pipeline instead of preparing it twice.

## Validation and limits

```bash
python -m pip install -e '.[web,pdf,test-web]'
python -m unittest discover -s tests -v
npm ci --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

API tests compare reports with the Python pipeline and cover upload replacement, quoted passage inspection, live-mode configuration/failure handling, malformed input, size limits, server-side secrets, and same-origin submissions. Frontend tests use React Testing Library and jsdom to exercise user interactions and stale-response handling.

**No public website has been deployed.** The supplied launcher serves locally and is not a multi-user authenticated service. Company deployment still needs its normal hosting, authentication and network setup. The managed browser could not access the local preview in this environment (`ERR_BLOCKED_BY_CLIENT`), so real-browser visual layout, mobile rendering and download behavior remain to be checked. Real Azure model access was not exercised.

The method is unchanged: paragraph/character chunking, no overlap, one regulation, a lexical shortlist for long regulation, exact quotation validation. No embeddings or temporal applicability checks were added.

Implementation references: [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/) and [FastAPI static serving](https://fastapi.tiangolo.com/tutorial/static-files/).
