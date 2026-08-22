"""Shared helpers for handling raw media bytes."""

import base64

import filetype


def to_data_url(data: bytes) -> str:
    """Encode raw image bytes as a base64 data URL with the detected MIME.

    The MIME is sniffed from the bytes rather than assumed: input images reach
    us from arbitrary URLs, and labelling a JPEG as ``image/png`` makes
    providers reject or misread it.
    """
    kind = filetype.guess(data)
    mime = kind.mime if kind else "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
