import pytest
from fastapi.testclient import TestClient

from app import config
from app.api import app

TOKEN = "test-token"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "TOKEN", TOKEN)
    return TestClient(app, headers={"X-Api-Token": TOKEN})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version(client, monkeypatch):
    monkeypatch.setattr(config, "VERSION", "1.2.3")
    r = client.get("/version")
    assert r.status_code == 200
    assert r.json() == {"version": "1.2.3"}


@pytest.mark.parametrize("headers", [{}, {"X-Api-Token": "wrong"}], ids=["missing", "wrong"])
def test_rejects_bad_token(client, headers):
    client.headers.pop("X-Api-Token")
    r = client.get("/health", headers=headers)
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid token"}


def test_cors_preflight_needs_no_token(client):
    client.headers.pop("X-Api-Token")
    r = client.options("/health", headers={
        "Origin": "http://localhost:4200",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-api-token",
    })
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_cors_allows_only_the_dev_origin(client):
    # Another dev copy on another port sets RLGYM_GUI_DEV_ORIGIN; it isn't allowed by default.
    r = client.options("/health", headers={
        "Origin": "http://localhost:4301",
        "Access-Control-Request-Method": "GET",
    })
    assert "access-control-allow-origin" not in r.headers
