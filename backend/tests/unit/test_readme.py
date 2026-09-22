"""Phase 8 — README must document setup and every registered route (spec 8.2)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

# Routes that are FastAPI/docs plumbing, not part of the public API surface.
_IGNORED_ROUTE_PREFIXES = ("/openapi.json", "/docs", "/redoc")


def test_readme_documents_env_setup():
    assert "cp .env.example .env" in README, "README must show how to create .env from .env.example"
    assert "docker compose up --build" in README, "README must show the one-command stack startup"
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    keys = [
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    ]
    missing = [k for k in keys if k not in README]
    assert not missing, f"README does not document env vars: {missing}"


def test_readme_documents_every_registered_route():
    from app.main import app

    documented, missing = [], []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path or path.startswith(_IGNORED_ROUTE_PREFIXES):
            continue
        documented.append(path)
        if path not in README:
            missing.append(path)
    assert not missing, f"README does not document routes: {missing}"
    assert len(documented) >= 7, f"Expected the full Phase 0-5 route surface, got {documented}"


def test_readme_documents_request_headers_and_streaming():
    assert "X-Routing-Strategy" in README, "README must document the strategy header"
    assert "Authorization" in README, "README must document bearer-token auth"
    assert "routing_metadata" in README, "README must document the terminal streaming event"
    assert "stream" in README, "README must mention streaming support"
