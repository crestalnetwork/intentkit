from intentkit.core.engine import _extract_text_content


def test_extract_from_list_mixed_types():
    content = [
        {"id": "rs_x", "summary": [], "type": "reasoning"},
        {
            "id": "ws_x",
            "action": {"query": "q", "type": "search"},
            "status": "completed",
            "type": "web_search_call",
        },
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": " World"},
    ]
    assert _extract_text_content(content) == "Hello World"


def test_extract_from_dict_text_type():
    content = {"type": "text", "text": "ABC"}
    assert _extract_text_content(content) == "ABC"


def test_extract_from_dict_with_text_without_type():
    content = {"text": "XYZ"}
    assert _extract_text_content(content) == "XYZ"


def test_extract_from_dict_without_text():
    content = {"type": "reasoning", "summary": []}
    assert _extract_text_content(content) == ""


def test_extract_from_string():
    assert _extract_text_content("plain") == "plain"
