from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import health
from app.main import create_app


def test_liveness_does_not_claim_dependency_readiness():
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503


@pytest.mark.parametrize("failure", [None, "redis", "mysql", "worker"])
def test_readiness_checks_dependencies_and_hides_errors(monkeypatch, failure):
    app = create_app()

    def check_worker():
        if failure == "mysql":
            raise RuntimeError("mysql://secret-password")
        return failure != "worker"

    app.state.rag_worker = SimpleNamespace(is_ready=check_worker)
    monkeypatch.setattr(health, "get_checkpointer", lambda: object())

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def ping(self):
            if failure == "redis":
                raise RuntimeError("redis://secret-password")

    monkeypatch.setattr(health.Redis, "from_url", lambda *args, **kwargs: Client())
    response = TestClient(app).get("/ready")
    assert response.status_code == (200 if failure is None else 503)
    assert "secret-password" not in response.text


def test_production_refuses_start_without_checkpoint(monkeypatch):
    from app import main

    @asynccontextmanager
    async def unavailable():
        yield None

    monkeypatch.setenv("RAG_ENVIRONMENT", "production")
    monkeypatch.setattr(main, "memory_lifespan", unavailable)
    with pytest.raises(RuntimeError, match="working Redis"), TestClient(create_app()):
        pass
    assert TestClient(create_app()).get("/openapi.json").status_code == 404
