"""Guard against drift between signing behavior and the team_only marker.

Wallet-signing tools must set ``team_only = True`` so guests of a published
agent never see them (ToolBindingMiddleware drops them per request); their
runtime ``ensure_signing_allowed`` call is only the second line of defense.
This test re-derives "signs" from the code (transitively: a tool class that
references a guarded signing helper, directly or through category helpers)
and compares it with the declared flag in both directions.
"""

import ast
from pathlib import Path

from intentkit.core.agent.tool_registry import get_tool_catalog
from intentkit.tools.base import collect_tool_classes, tool_field_default

TOOLS_DIR = Path(__file__).resolve().parents[2] / "intentkit" / "tools"


def _seed_guarded_names() -> set[str]:
    """Signing helpers, derived from onchain.py: ensure_signing_allowed plus
    every method whose body calls it (get_wallet_signer, ...). Deriving keeps
    this test honest when new guarded helpers are added to the base class."""
    tree = ast.parse((TOOLS_DIR / "onchain.py").read_text())
    funcs = {
        n.name: _refs(n)
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    seed = {"ensure_signing_allowed"}
    changed = True
    while changed:
        changed = False
        for fname, r in funcs.items():
            if fname not in seed and r & seed:
                seed.add(fname)
                changed = True
    return seed


def _refs(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        if isinstance(n, ast.Name):
            out.add(n.id)
    return out


def _signing_tool_names(category: str) -> set[str]:
    files = {
        py: ast.parse(py.read_text())
        for py in sorted((TOOLS_DIR / category).rglob("*.py"))
    }
    # Transitive closure: helpers that wrap signing helpers are guarded too.
    funcs: dict[str, set[str]] = {}
    for tree in files.values():
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.setdefault(n.name, set()).update(_refs(n))
    guarded = _seed_guarded_names()
    changed = True
    while changed:
        changed = False
        for fname, r in funcs.items():
            if fname not in guarded and r & guarded:
                guarded.add(fname)
                changed = True

    signing: set[str] = set()
    for tree in files.values():
        consts = {
            n.targets[0].id: n.value.value
            for n in tree.body
            if isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and isinstance(n.value, ast.Constant)
        }
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            tool_name = None
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and getattr(stmt.target, "id", "") == "name"
                ):
                    if isinstance(stmt.value, ast.Constant):
                        tool_name = stmt.value.value
                    elif isinstance(stmt.value, ast.Name):
                        tool_name = consts.get(stmt.value.id)
            if isinstance(tool_name, str) and _refs(node) & guarded:
                signing.add(tool_name)
    return signing


def test_signing_tools_are_marked_team_only():
    # Scan every category, not just wallet-flagged ones: a signing tool
    # accidentally added to a themed (or unflagged) category must be caught
    # too, or it would ship without the team_only guest guard.
    catalog = get_tool_catalog()
    flags = {}
    for cls in collect_tool_classes():
        name = tool_field_default(cls, "name")
        if isinstance(name, str) and name:
            flags[name] = bool(tool_field_default(cls, "team_only"))

    problems = []
    for category in sorted(catalog):
        signing = _signing_tool_names(category)
        for tool_name in catalog[category]["tools"]:
            expected = tool_name in signing
            actual = flags.get(tool_name, False)
            if expected and not actual:
                problems.append(f"{category}/{tool_name}: signs but team_only is False")
            if actual and not expected:
                problems.append(
                    f"{category}/{tool_name}: team_only but no signing path found"
                )
    assert not problems, "\n".join(problems)
