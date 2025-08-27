from fastapi.testclient import TestClient
from backend.app.main import app


def test_health() -> None:
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
