"""Local web adapter. Credentials and model requests stay on the Python server."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from green_claims.config import Settings
from green_claims.demo.fixtures import demo_regulation, load_cases
from green_claims.ingestion.parsers import MAX_FILE_BYTES, parse_document
from green_claims.pipeline import prepare, run_review


def create_app(settings: Settings | None = None, *, dbutils=None, static_dir: Path | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Green Claims Review", version="0.3.0", docs_url=None, redoc_url=None)

    def live_available():
        return bool(settings.api_url.strip() and settings.model.strip() and (
            os.getenv("AZURE_OPENAI_API_KEY") or
            (settings.secret_scope and settings.secret_key and dbutils is not None)
        ))

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # The browser uses the same origin (Vite proxies /api during development).
        # Refuse cross-origin form submissions to a locally configured model endpoint.
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin requests are not supported."}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Do not echo submitted material back in validation error payloads.
        return JSONResponse({"detail": "Invalid request. Check the input lengths, mode and regulation selection."}, status_code=422)

    @app.get("/api/config")
    def config():
        return {"live_available": live_available(), "max_file_bytes": MAX_FILE_BYTES,
                "max_disclosure_chars": 35_000, "max_claims": 15}

    @app.get("/api/cases")
    def cases():
        return [{"id": c["id"], "name": c["name"], "claims": c["claims"], "disclosure": c["disclosure"]}
                for c in load_cases()]

    @app.post("/api/reviews")
    def review(
        claims: Annotated[str, Form(min_length=1, max_length=30_015)],
        disclosure: Annotated[str, Form(min_length=1, max_length=35_000)],
        mode: Annotated[Literal["Offline demo", "Live AI"], Form()] = "Offline demo",
        verification: Annotated[Literal["none", "facts", "facts_and_judge"], Form()] = "none",
        regulation_source: Annotated[Literal["demo", "upload", "none"], Form()] = "demo",
        version: Annotated[str, Form(max_length=200)] = "Not specified",
        regulation_file: Annotated[UploadFile | None, File()] = None,
    ):
        try:
            if regulation_source == "upload":
                if regulation_file is None:
                    raise HTTPException(422, "Choose a PDF, TXT or Markdown regulation file first.")
                content = regulation_file.file.read(MAX_FILE_BYTES + 1)
                if len(content) > MAX_FILE_BYTES:
                    raise HTTPException(413, "Regulation must be at most 10 MB.")
                regulation = parse_document(regulation_file.filename or "regulation.txt", content, version)
            else:
                if regulation_file is not None:
                    raise HTTPException(422, "Select Upload regulation to use the attached file.")
                regulation = demo_regulation() if regulation_source == "demo" else None
            # Validate inputs before attempting to obtain credentials or call a model.
            context = prepare(claims, disclosure, regulation)
            if mode == "Live AI" and not live_available():
                raise HTTPException(503, "Live AI is not configured on this server. Configure the endpoint, deployment and server-side credentials.")
            client = None
            if mode == "Live AI":
                try:
                    client = settings.make_client(dbutils)
                except Exception:
                    raise HTTPException(503, "Server-side model credentials could not be loaded.") from None
            report = run_review(claims, disclosure, regulation, mode,
                                generator=client, model=settings.model, language=settings.language,
                                verification=verification)
            # Separate source inspection data from the unchanged pipeline report schema.
            return {"report": report, "sources": {
                "disclosure": [asdict(p) for p in context["disclosure"]],
                "regulation": [asdict(p) for p in context["selected_regulation"]],
            }}
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except Exception:
            # Company SDK failures can contain provider payloads; never return those.
            raise HTTPException(500, "Analysis did not complete. Check the server configuration and model connection.") from None
        finally:
            if regulation_file is not None:
                regulation_file.file.close()

    if static_dir is not None:
        directory = Path(static_dir).resolve()
        if not (directory / "index.html").is_file():
            raise ValueError("Build the frontend first: cd frontend && npm ci && npm run build")
        app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
    return app


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Serve the Green Claims web application locally")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--static-dir", type=Path, default=Path("frontend/dist"))
    parser.add_argument("--api-only", action="store_true", help="Use with the Vite development server")
    args = parser.parse_args()
    app = create_app(static_dir=None if args.api_only else args.static_dir)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
