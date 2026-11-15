from fastapi.testclient import TestClient

from toolgate.api import create_app


def test_home_and_cases() -> None:
    client = TestClient(create_app())
    home = client.get("/")
    assert home.status_code == 200
    assert "toolgate" in home.text

    css = client.get("/static/styles.css")
    assert css.status_code == 200
    assert "Sora" in css.text or "--teal" in css.text

    cases = client.get("/cases")
    assert cases.status_code == 200
    payload = cases.json()
    assert len(payload) >= 8
    assert any(item["case_id"] == "case_cross_tenant" for item in payload)
