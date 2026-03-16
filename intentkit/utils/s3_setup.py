"""Deprecated: moved to intentkit.clients.s3_setup."""


def __getattr__(name: str):
    if name == "ensure_bucket_exists_and_public":
        from intentkit.clients.s3_setup import ensure_bucket_exists_and_public

        return ensure_bucket_exists_and_public
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
