from types import SimpleNamespace

from intentkit.core.engine import extract_text_content, extract_thinking_content


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
    assert extract_text_content(content) == "Hello World"


def test_extract_from_dict_text_type():
    content = {"type": "text", "text": "ABC"}
    assert extract_text_content(content) == "ABC"


def test_extract_from_dict_with_text_without_type():
    content = {"text": "XYZ"}
    assert extract_text_content(content) == "XYZ"


def test_extract_from_dict_without_text():
    content = {"type": "reasoning", "summary": []}
    assert extract_text_content(content) == ""


def test_extract_from_string():
    assert extract_text_content("plain") == "plain"


# Helper to create a fake AIMessage-like object
def _msg(content=None, additional_kwargs=None):
    return SimpleNamespace(
        content=content or [],
        additional_kwargs=additional_kwargs or {},
    )


# Tests for extract_thinking_content


def test_thinking_additional_kwargs_reasoning_content():
    """OpenRouter / DeepSeek / xAI: reasoning_content string in additional_kwargs."""
    msg = _msg(
        content=[{"type": "text", "text": "Hello"}],
        additional_kwargs={"reasoning_content": "I am reasoning about this."},
    )
    assert extract_thinking_content(msg) == "I am reasoning about this."


def test_thinking_additional_kwargs_reasoning_v0():
    """OpenAI Responses API v0 compat: reasoning dict with summary list."""
    msg = _msg(
        additional_kwargs={
            "reasoning": {
                "summary": [
                    {"type": "summary_text", "text": "Step one."},
                    {"type": "summary_text", "text": "Step two."},
                ],
                "id": "rs_1",
            }
        },
    )
    assert extract_thinking_content(msg) == "Step one.\n\nStep two."


def test_thinking_content_reasoning_standard():
    """langchain-core standard: type=reasoning with reasoning field."""
    msg = _msg(
        content=[
            {"type": "reasoning", "reasoning": "My reasoning text."},
            {"type": "text", "text": "Hello"},
        ],
    )
    assert extract_thinking_content(msg) == "My reasoning text."


def test_thinking_content_reasoning_summary_list():
    """OpenAI Responses API: type=reasoning with summary list in content."""
    msg = _msg(
        content=[
            {
                "type": "reasoning",
                "id": "rs_1",
                "summary": [
                    {"type": "summary", "text": "First thought."},
                    {"type": "summary", "text": "Second thought."},
                ],
            },
            {"type": "text", "text": "Hello"},
        ],
    )
    assert extract_thinking_content(msg) == "First thought.\n\nSecond thought."


def test_thinking_content_reasoning_direct_text():
    """Fallback: type=reasoning with direct text field."""
    msg = _msg(
        content=[
            {"type": "reasoning", "text": "I am thinking about this."},
            {"type": "text", "text": "Response"},
        ],
    )
    assert extract_thinking_content(msg) == "I am thinking about this."


def test_thinking_content_thinking_block():
    """Anthropic / Google Gemini: type=thinking with thinking field."""
    msg = _msg(
        content=[
            {"type": "thinking", "thinking": "Claude's extended thinking here."},
            {"type": "text", "text": "Response"},
        ],
    )
    assert extract_thinking_content(msg) == "Claude's extended thinking here."


def test_thinking_no_reasoning_blocks():
    msg = _msg(content=[{"type": "text", "text": "Hello"}])
    assert extract_thinking_content(msg) is None


def test_thinking_no_content_no_kwargs():
    msg = _msg()
    assert extract_thinking_content(msg) is None


def test_thinking_empty_summary():
    msg = _msg(
        content=[{"type": "reasoning", "id": "rs_1", "summary": []}],
    )
    assert extract_thinking_content(msg) is None


def test_thinking_plain_object_without_attrs():
    """Object without content/additional_kwargs returns None."""
    assert extract_thinking_content(object()) is None
