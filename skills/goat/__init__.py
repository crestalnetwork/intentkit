"""Goat skills."""

import importlib
import secrets
import time
from dataclasses import is_dataclass
from typing import (
    Any,
    Dict,
    Literal,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

import httpx
from eth_account import Account
from eth_utils import encode_hex
from goat import WalletClientBase
from goat.classes.plugin_base import PluginBase
from goat_adapters.langchain import get_on_chain_tools
from goat_wallets.crossmint import crossmint

from abstracts.skill import SkillStoreABC
from skills.goat.base import GoatBaseTool
from utils.chain import ChainConfig, NetworkType

from .base import base_url

# TODO: add the configuration of the chains to a proper place. https://docs.crossmint.com/introduction/supported-chains
crossmint_chains = {
    "base": ChainConfig(
        "base",
        NetworkType.Mainnet,
        "https://base-mainnet.g.alchemy.com/v2/demo",
        "https://base-mainnet.g.alchemy.com/v2/demo",
    ),
    "arbitrum": ChainConfig(
        "arbitrum",
        NetworkType.Mainnet,
        "https://arb-mainnet.g.alchemy.com/v2/demo",
        "https://arb-mainnet.g.alchemy.com/v2/demo",
    ),
}


def create_smart_wallet(api_key: str, signer_address: str) -> Dict:
    url = f"{base_url}/api/v1-alpha2/wallets"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
    }

    js = {
        "type": "evm-smart-wallet",
        "config": {
            "adminSigner": {
                "type": "evm-keypair",
                "address": signer_address,
            },
        },
    }

    with httpx.Client() as client:
        try:
            response = client.post(url, headers=headers, json=js)
            response.raise_for_status()
            json_dict = response.json()

            if "error" in json_dict:
                raise Exception(f"Failed to create wallet: {json_dict}")

            return json_dict
        except httpx.RequestError as req_err:
            raise Exception(f"request error from Crossmint API: {req_err}") from req_err
        except httpx.HTTPStatusError as http_err:
            raise Exception(f"http error from Crossmint API: {http_err}") from http_err
        except Exception as e:
            raise Exception(f"error from Crossmint API: {e}") from e


def create_smart_wallets_if_not_exist(api_key: str, wallet_data: dict | None):
    evm_wallet_data = wallet_data.get("evm") if wallet_data else None
    # no wallet data or private_key is empty
    if not evm_wallet_data or not evm_wallet_data.get("private_key"):
        evm_wallet_data = evm_wallet_data or {}

        if evm_wallet_data.get("address"):
            raise Exception(
                "smart wallet address is present but private key is not provided"
            )

        # Generate a random 256-bit (32-byte) private key
        private_key_bytes = secrets.token_bytes(32)
        # Encode the private key to a hexadecimal string
        evm_wallet_data["private_key"] = encode_hex(private_key_bytes)

        signer_address = Account.from_key(evm_wallet_data["private_key"]).address

        new_smart_wallet = create_smart_wallet(api_key, signer_address)
        if not new_smart_wallet or not new_smart_wallet.get("address"):
            raise RuntimeError("Failed to create smart wallet")

        evm_wallet_data["address"] = new_smart_wallet["address"]
        # put an sleep to prevent 429 error

    if not evm_wallet_data.get("address"):
        raise Exception("smart wallet address is empty")

    return {"evm": evm_wallet_data}


def init_smart_wallets(
    api_key: str,
    chain_configs: Dict[str, ChainConfig],
    wallet_data: dict | None,
):
    # Create Crossmint client
    crossmint_client = crossmint(api_key)

    wallets = []
    for chain_name, chain_config in chain_configs.items():
        wallet = crossmint_client["smartwallet"](
            {
                "address": wallet_data["address"],
                "signer": {
                    "secretKey": wallet_data["private_key"],
                },
                "provider": chain_config.rpc_url,
                "ensProvider": chain_config.ens_url,
                "chain": chain_name,
            }
        )
        wallets.append(wallet)
        time.sleep(1)

    return wallets


def resolve_optional_type(field_type: Type) -> Type:
    if hasattr(field_type, "__origin__") and get_origin(field_type) is Union:
        args = get_args(field_type)
        if (
            type(None) in args and len(args) == 2
        ):  # Check if None is one of the types in Union and there are 2 types
            return next(t for t in args if t is not type(None))
    return field_type


def resolve_type(val: str, mod) -> Any:
    try:
        return getattr(mod, val)
    except AttributeError:
        try:
            mod_path, cls_name = val.rsplit(".", 1)
            type_mod = importlib.import_module(mod_path)
            return getattr(type_mod, cls_name)
        except (ValueError, ImportError, AttributeError) as e:
            raise ValueError(f"type '{val}' could not be resolved") from e


def resolve_value(val: Any, f_type: Type, mod) -> Any:
    f_type = resolve_optional_type(f_type)

    if f_type in (str, int, float, bool):
        return f_type(val)

    if hasattr(f_type, "__origin__"):
        if f_type.__origin__ is list:
            if not isinstance(val, list):
                raise ValueError(f"expected list object but got {type(val).__name__}")

            elem_type = f_type.__args__[0]
            return [resolve_value(item, elem_type, mod) for item in val]
        if f_type.__origin__ is Literal:
            literal_items = f_type.__args__
            if val not in literal_items:
                raise ValueError(f"not supported literal value {type(val)}")

            return val

    if isinstance(val, str):
        return resolve_type(val, mod)

    raise ValueError(f"unsupported type: {f_type}")


def get_goat_skill(
    wallet: WalletClientBase,
    plugin_configs: Dict[str, Any],
    skill_store: SkillStoreABC,
    agent_store: SkillStoreABC,
    agent_id: str,
) -> list[GoatBaseTool]:
    if not wallet:
        raise ValueError("GOAT crossmint wallet is empty")

    plugins = []
    for p_name, p_options in plugin_configs.items():
        try:
            mod = importlib.import_module(f"goat_plugins.{p_name}")

            initializer = getattr(mod, p_name)
            hints = get_type_hints(initializer)

            opt_type = hints.get("options")
            if not opt_type:
                raise ValueError(
                    f"GOAT plugin {p_name} does not have associated options"
                )

            opt_type = resolve_optional_type(opt_type)
            if not is_dataclass(opt_type):
                raise ValueError(f"GOAT plugin {p_name} options is malformed")

            fields = get_type_hints(opt_type)

            resolved_vals = {}
            raw_args = p_options

            for f_name, f_type in fields.items():
                if f_name not in raw_args:
                    if f_type.__name__.upper() == "OPTIONAL":
                        continue
                    raise ValueError(
                        f"GOAT plugin {p_name} should have {f_name} option"
                    )

                val = raw_args[f_name]

                try:
                    resolved_val = resolve_value(val, f_type, mod)
                    resolved_vals[f_name] = resolved_val

                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"GOAT field {f_name} has invalid value, plugin name {p_name} : {str(e)}"
                    )

            plugin_options = opt_type(**resolved_vals)

            plugin: PluginBase = initializer(options=plugin_options)
            plugins.append(plugin)

        except AttributeError:
            raise Exception(f"GOAT initializer function not found: {p_name}")
        except ImportError:
            raise Exception(f"GOAT plugin load failed: {p_name}")
        except Exception as e:
            raise Exception(f"GOAT plugin initialization failed: {p_name}: {str(e)}")

    tools = []
    try:
        for p_name, plugin in plugins.items():
            p_tools = get_on_chain_tools(
                wallet=wallet,
                plugins=[plugin],
            )
            time.sleep(0.2)

        p_tools = get_on_chain_tools(
            wallet=wallet,
            plugins=plugins,
        )
        for t in p_tools:
            t.name = f"goat_{t.name.replace(".", "_")}"
            t.description = f"This is plugin of GOAT tool, {t.description}"
        tools.extend(p_tools)

    except Exception as e:
        raise Exception(f"GOAT tools initiation failed: {str(e)}")

    return tools
