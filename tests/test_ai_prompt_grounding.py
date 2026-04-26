from nwn_persona_web.chat_processing import _build_reply_messages


def test_reply_prompt_grounds_selected_message_and_recent_chat():
    messages = _build_reply_messages(
        character_name="Elvith Ma'for",
        player_name="Dolin Schneim",
        player_message="We are. Pereppi.",
        persona={
            "persona": "A precise noble mage.",
            "traits": ["observant"],
            "mannerisms": ["measured"],
        },
        context={
            "messages": [
                {"speaker": "Dolin Schneim", "text": "The armor spreader helps."},
                {
                    "speaker": "Elvith Ma'for",
                    "text": "*A gesture of agreement* Indeed; very clever.",
                },
                {
                    "speaker": "Elvith Ma'for",
                    "text": "So, are we awaiting someone?",
                },
                {"speaker": "Dolin Schneim", "text": "We are. Pereppi."},
            ]
        },
        context_summary={},
        creativity_instruction="",
    )

    prompt_text = "\n\n".join(message["content"] for message in messages)

    assert "Selected latest message from Dolin Schneim to Elvith Ma'for" in prompt_text
    assert "So, are we awaiting someone?" in prompt_text
    assert "We are. Pereppi." in prompt_text
    assert "Do not treat a name or short answer as a mysterious abstract topic" in prompt_text
    assert "answer it directly" in prompt_text.lower()
