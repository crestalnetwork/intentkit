"""YAML loading that prefers libyaml.

PyYAML's pure-Python ``SafeLoader`` is roughly 18x slower than the libyaml-backed
``CSafeLoader`` on this repo's agent definitions (44ms vs 2.4ms for the 34 files
in ``public_agents/``). The C loader ships in PyYAML's binary wheels, but a
source install built without the libyaml headers does not have it, so fall back
rather than making it a hard requirement.

Both loaders implement the same safe subset — no arbitrary object construction —
so this is a drop-in replacement for ``yaml.safe_load``.
"""

from typing import IO, Any

import yaml

try:
    from yaml import CSafeLoader as _SafeLoader
except ImportError:  # pragma: no cover - depends on how PyYAML was built
    from yaml import SafeLoader as _SafeLoader

#: True when the libyaml-backed loader is in use, i.e. the fast path.
USING_LIBYAML = _SafeLoader is not yaml.SafeLoader


def safe_load(stream: str | bytes | IO[str] | IO[bytes]) -> Any:
    """Parse a YAML document, using libyaml when it is available."""
    return yaml.load(stream, Loader=_SafeLoader)
