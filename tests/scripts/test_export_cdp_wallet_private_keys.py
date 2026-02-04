from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "export_cdp_wallet_private_keys.py"
    )
    spec = spec_from_file_location("export_cdp_wallet_private_keys", script_path)
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load script module")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_private_key_adds_prefix():
    module = load_script_module()
    assert module.normalize_private_key("abcd") == "0xabcd"


def test_normalize_private_key_keeps_prefix():
    module = load_script_module()
    assert module.normalize_private_key("0xABCD") == "0xABCD"


def test_normalize_private_key_empty():
    module = load_script_module()
    assert module.normalize_private_key("") == ""
