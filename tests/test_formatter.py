from app.formatter import format_message
from app.models import MessagePayload


def test_format_message_structure():
    payload = MessagePayload(
        text="Hello world",
        source_title="Source",
        original_link="https://t.me/source/1",
        matched_keywords=["hello"],
        matched_links=["https://example.com"],
    )
    result = format_message(payload)
    lines = result.split("\n")
    assert lines[0] == "Hello world"
    assert lines[1] == ""
    assert "Matched keywords: hello" in result
    assert "Matched links: https://example.com" in result
    assert "Source: Source" in result
    assert "Original: https://t.me/source/1" in result


def test_format_message_no_duplication():
    payload = MessagePayload(
        text="Line1",
        source_title="Src",
        original_link=None,
        matched_keywords=[],
        matched_links=[],
    )
    result = format_message(payload)
    assert result.count("Line1") == 1
