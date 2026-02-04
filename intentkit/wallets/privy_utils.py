import json
import textwrap
from typing import Any

from hexbytes import HexBytes


def _canonicalize_json(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    if isinstance(value, str):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    # Handle bytes and HexBytes by converting to hex string
    if isinstance(value, (bytes, HexBytes)):
        hex_str = value.hex()
        if not hex_str.startswith("0x"):
            hex_str = f"0x{hex_str}"
        return json.dumps(hex_str, separators=(",", ":"), ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonicalize_json(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        parts: list[str] = []
        for k in keys:
            if not isinstance(k, str):
                raise TypeError("JSON object keys must be strings")
            parts.append(_canonicalize_json(k) + ":" + _canonicalize_json(value[k]))
        return "{" + ",".join(parts) + "}"
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _privy_private_key_to_pem(key: str) -> bytes:
    private_key_as_string = key.replace("wallet-auth:", "").strip()
    wrapped = "\n".join(textwrap.wrap(private_key_as_string, width=64))
    pem = f"-----BEGIN PRIVATE KEY-----\n{wrapped}\n-----END PRIVATE KEY-----\n"
    return pem.encode("utf-8")


def _sanitize_for_json(value: object) -> object:
    """Recursively convert bytes and HexBytes to hex strings for JSON serialization.

    This is needed when passing data structures to httpx's json= parameter,
    which uses standard json.dumps() that doesn't support bytes.
    """
    if isinstance(value, (bytes, HexBytes)):
        hex_str = value.hex()
        if not hex_str.startswith("0x"):
            hex_str = f"0x{hex_str}"
        return hex_str
    elif isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_sanitize_for_json(item) for item in value]
    else:
        return value


def _convert_typed_data_to_privy_format(typed_data: dict[str, Any]) -> dict[str, Any]:
    """Convert EIP-712 typed data to Privy's expected format.

    Privy API expects snake_case field names but EIP-712 uses camelCase.
    Main conversion: primaryType -> primary_type
    """
    result = dict(typed_data)

    # Convert primaryType to primary_type
    if "primaryType" in result:
        result["primary_type"] = result.pop("primaryType")

    return result
