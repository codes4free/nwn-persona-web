from nwn_persona_web.auth import hash_password, is_password_hash, verify_password


def test_hash_password_does_not_store_plain_text():
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert is_password_hash(password_hash)
    assert verify_password(password_hash, "correct horse battery staple")
    assert not verify_password(password_hash, "wrong")


def test_verify_password_accepts_legacy_plain_text():
    assert verify_password("legacy-password", "legacy-password")
    assert not verify_password("legacy-password", "wrong")
