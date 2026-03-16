"""Utility exports for IntentKit."""


def __getattr__(name: str):
    if name == "resolve_ens_to_address":
        from intentkit.clients.web3_ens import resolve_ens_to_address

        return resolve_ens_to_address
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
