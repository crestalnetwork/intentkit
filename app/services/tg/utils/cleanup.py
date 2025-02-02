import re


def remove_bot_name(bot_uname, message_text) -> str:
    clean_text = message_text.replace(f"@{bot_uname} ", "")
    clean_text = clean_text.replace(f"@{bot_uname}", "")
    return clean_text


def clean_token_str(token) -> str:
    return re.sub(r"\s+", "", token)
