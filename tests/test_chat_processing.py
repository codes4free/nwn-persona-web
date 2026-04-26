from nwn_roleplay_helper.chat_processing import process_new_messages


class FakeSocketIO:
    def __init__(self):
        self.events = []

    def emit(self, event, payload):
        self.events.append((event, payload))


def test_hm_chat_markup_is_preserved_as_player_message():
    socketio = FakeSocketIO()

    process_new_messages(
        "[Viper's Wit] Auguste Detourne: [Talk] <c>[HM]</c> Good day, Monsieur.",
        client="D6lab",
        user_characters={},
        character_profiles={},
        socketio=socketio,
    )

    new_messages = [
        payload for event, payload in socketio.events if event == "new_message"
    ]
    player_messages = [
        payload for event, payload in socketio.events if event == "player_message"
    ]

    assert new_messages
    assert "Auguste Detourne" in new_messages[0]["message"]
    assert "[HM] Good day, Monsieur." in new_messages[0]["message"]
    assert player_messages[0]["player_name"] == "Auguste Detourne"
    assert player_messages[0]["message"] == "[HM] Good day, Monsieur."
