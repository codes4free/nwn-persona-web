from app import app


def test_login_page_loads():
    client = app.test_client()
    resp = client.get("/login")
    assert resp.status_code == 200


def test_register_page_loads():
    client = app.test_client()
    resp = client.get("/register")
    assert resp.status_code == 200


def test_debug_routes_require_login():
    client = app.test_client()

    for path in ("/debug", "/debug_last_log", "/debug_websocket", "/socket_test"):
        resp = client.get(path)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


def test_ai_routes_require_login():
    client = app.test_client()

    for path in ("/api/respond", "/api/translate", "/set_openai_token"):
        resp = client.post(path, json={})
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
