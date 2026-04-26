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


def test_debug_routes_are_disabled_by_default_for_logged_in_users():
    client = app.test_client()
    app.config["ENABLE_DEBUG_TOOLS"] = False

    with client.session_transaction() as sess:
        sess["user"] = "tester"

    for path in ("/debug", "/debug_last_log", "/debug_websocket", "/socket_test"):
        resp = client.get(path)
        assert resp.status_code == 404


def test_debug_routes_can_be_enabled_for_logged_in_users():
    client = app.test_client()
    app.config["ENABLE_DEBUG_TOOLS"] = True

    with client.session_transaction() as sess:
        sess["user"] = "tester"

    resp = client.get("/debug_websocket")
    assert resp.status_code == 200

    app.config["ENABLE_DEBUG_TOOLS"] = False


def test_ai_routes_require_login():
    client = app.test_client()

    for path in ("/api/respond", "/api/translate", "/set_openai_token"):
        resp = client.post(path, json={})
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
