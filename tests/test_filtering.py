from app.filtering import match_keywords, normalize_text


def test_normalize_text_collapses_whitespace():
    text = "  Hello   World\n\nTest  "
    assert normalize_text(text) == "hello world test"


def test_match_keywords_case_insensitive():
    text = "This has VPN and Security"
    keywords = ["vpn", "alert"]
    assert match_keywords(text, keywords) == ["vpn"]


def test_match_keywords_no_match():
    text = "No hits here"
    keywords = ["vpn"]
    assert match_keywords(text, keywords) == []
