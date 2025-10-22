#!/usr/bin/env python3
"""
Simple import validation script for IntentKit project.
"""

import ast
from pathlib import Path


def check_file_imports(file_path):
    """Check imports in a single file."""
    print(f"Checking: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    print(f"  Import: {alias.name} (line {node.lineno})")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    print(f"  From: {node.module} (line {node.lineno})")

    except Exception as e:
        print(f"  Error: {e}")


def main():
    """Main function."""
    print("Simple import checker")

    # Check a few key files
    intentkit_dir = Path("../intentkit")

    if intentkit_dir.exists():
        print(f"Found intentkit directory: {intentkit_dir.absolute()}")

        # Check a few key files
        key_files = [
            intentkit_dir / "__init__.py",
            intentkit_dir / "core" / "agent.py",
            intentkit_dir / "models" / "agent.py",
        ]

        for file_path in key_files:
            if file_path.exists():
                check_file_imports(file_path)
            else:
                print(f"File not found: {file_path}")
    else:
        print(f"IntentKit directory not found: {intentkit_dir.absolute()}")


if __name__ == "__main__":
    main()
