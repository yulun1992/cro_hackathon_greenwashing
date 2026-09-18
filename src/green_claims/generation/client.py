"""HTTP adapter; no credential persistence and no redirects."""
import json
import socket
from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlparse
from green_claims.generation.context import build_messages
from green_claims.validation.findings import validate_findings

def request_analysis(context: dict, api_url: str, model: str, api_key: str = "",
                  auth_type: str = "bearer", language: str = "English"):
    parsed = urlparse(api_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Enter a full HTTP(S) chat/completions endpoint without credentials in its URL.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS for remote endpoints. HTTP is allowed only for localhost.")
    if not model.strip():
        raise ValueError("Enter a model or deployment name.")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key" if auth_type == "api-key" else "Authorization"] = api_key if auth_type == "api-key" else f"Bearer {api_key}"
    body = {"model": model.strip(), "messages": build_messages(context, language)}
    # No provider-specific response_format/temperature parameters; JSON is validated locally.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    request = Request(api_url.strip(), data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=120) as response:
            response_bytes = response.read(2_000_001)
        if len(response_bytes) > 2_000_000:
            raise ValueError("Model response exceeds the size limit.")
    except (TimeoutError, socket.timeout) as exc:
        raise ValueError("Model request timed out. Try a shorter input or check your endpoint.") from exc
    except HTTPError as exc:
        raise ValueError(f"Model endpoint returned HTTP {exc.code}. Check authentication, model name and endpoint configuration.") from exc
    except URLError as exc:
        raise ValueError("Cannot connect to the model endpoint. Check its URL and network access.") from exc
    try:
        envelope = json.loads(response_bytes)
        choice = envelope["choices"][0]
        if choice.get("finish_reason") in {"length", "content_filter"}:
            raise ValueError("The model response was truncated or filtered. Shorten inputs and retry.")
        content = choice["message"]["content"].strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else content
        raw = json.loads(content)
    except (KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise ValueError("The endpoint did not return the expected JSON. Use a chat model with reliable JSON output and retry.") from exc
    return raw


class Generator(Protocol):
    def generate(self, context: dict, language: str = "English") -> dict: ...

@dataclass(frozen=True)
class ChatCompletionsClient:
    api_url: str
    model: str
    api_key: str = field(default="", repr=False)
    auth_type: str = "api-key"

    def __post_init__(self):
        if self.auth_type not in {"api-key", "bearer"}:
            raise ValueError("Authentication must be api-key or bearer.")

    def generate(self, context: dict, language: str = "English") -> dict:
        return request_analysis(context, self.api_url, self.model, self.api_key, self.auth_type, language)


def live_analysis(context, api_url, model, api_key="", auth_type="bearer", language="English"):
    """Compatibility entry point for the original adapter contract."""
    raw = ChatCompletionsClient(api_url, model, api_key, auth_type).generate(context, language)
    return validate_findings(raw, context)
