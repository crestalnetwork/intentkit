"""Tests for the libyaml-preferring YAML loader."""

import io

import pytest
import yaml as pyyaml

from intentkit.utils.yaml import USING_LIBYAML, safe_load

DOC = """
slug: demo
name: Demo Agent
tags:
  - alpha
  - beta
nested:
  count: 3
  enabled: true
  ratio: 1.5
  nothing: null
text: |
  line one
  line two
unicode: 中文字符
"""


@pytest.mark.parametrize(
    "source",
    [DOC, DOC.encode(), io.StringIO(DOC), io.BytesIO(DOC.encode())],
    ids=["str", "bytes", "text-stream", "binary-stream"],
)
def test_accepts_the_same_sources_as_pyyaml(source):
    """str, bytes and both stream flavours parse identically."""
    assert safe_load(source) == pyyaml.safe_load(DOC)


def test_matches_pure_python_safe_load():
    """The C loader must not change parsing semantics."""
    assert safe_load(DOC) == pyyaml.load(DOC, Loader=pyyaml.SafeLoader)


def test_empty_document_is_none():
    """Callers rely on a falsy result to detect empty files."""
    assert safe_load("") is None


def test_rejects_arbitrary_object_construction():
    """Still the *safe* subset — no python/object tags."""
    with pytest.raises(pyyaml.YAMLError):
        safe_load("!!python/object/apply:os.system ['echo pwned']")


def test_reports_which_loader_is_active():
    """The flag is what tells us whether the fast path is in play."""
    assert isinstance(USING_LIBYAML, bool)
    if USING_LIBYAML:
        assert hasattr(pyyaml, "CSafeLoader")
