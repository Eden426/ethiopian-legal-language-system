from fastapi.testclient import TestClient

from src.api.app import app


def test_health_returns_service_status() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ethiopian-legal-language-system",
    }


def test_translation_rejects_empty_text() -> None:
    client = TestClient(app)

    response = client.post("/v1/translate", json={"text": ""})

    assert response.status_code == 422


def test_translation_contract_reports_service_not_ready() -> None:
    client = TestClient(app)

    response = client.post("/v1/translate", json={"text": "የሙከራ ጽሑፍ"})

    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "service_not_ready"


def test_openapi_contains_all_mvp_contracts() -> None:
    client = TestClient(app)

    schema = client.get("/openapi.json").json()

    assert {"/v1/translate", "/v1/search", "/v1/answer"} <= schema["paths"].keys()
