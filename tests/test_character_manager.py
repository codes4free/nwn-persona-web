import json

import character_manager


def _write_profile(path, name, owner="tester"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": name,
                "owner": owner,
                "race": "Human",
                "class": "Commoner",
                "alignment": "Neutral",
                "description": "A test character",
                "background": "Testing",
                "appearance": "Plain",
                "traits": ["careful"],
            }
        ),
        encoding="utf-8",
    )


def test_update_profile_finds_raw_filename_with_spaces_and_apostrophe(
    tmp_path, monkeypatch
):
    profiles_dir = tmp_path / "character_profiles"
    monkeypatch.setattr(character_manager, "CHARACTER_PROFILES_DIR", str(profiles_dir))
    character_name = "Marvin'ael Starbreeze"
    profile_path = profiles_dir / "fullgazz" / f"{character_name}.json"
    _write_profile(profile_path, character_name)

    result = character_manager.update_profile(character_name, {"temperature": 0.1})

    assert result["success"] is True
    updated = json.loads(profile_path.read_text(encoding="utf-8"))
    assert updated["name"] == character_name
    assert updated["temperature"] == 0.1


def test_get_and_delete_profile_find_legacy_underscored_filename(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "character_profiles"
    monkeypatch.setattr(character_manager, "CHARACTER_PROFILES_DIR", str(profiles_dir))
    character_name = "Elvith Ma'for"
    profile_path = profiles_dir / "fullgazz" / "Elvith_Ma'for.json"
    _write_profile(profile_path, character_name)

    assert character_manager.get_profile(character_name)["name"] == character_name

    result = character_manager.delete_profile(character_name)

    assert result["success"] is True
    assert not profile_path.exists()
