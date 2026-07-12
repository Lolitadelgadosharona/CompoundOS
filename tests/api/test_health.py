from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_root_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}
