from app import app


def test_login_page_loads():
    client = app.test_client()
    resp = client.get("/login")
    assert resp.status_code == 200


def test_register_page_loads():
    client = app.test_client()
    resp = client.get("/register")
    assert resp.status_code == 200
