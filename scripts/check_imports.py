#!/usr/bin/env python3
"""
Import validation script for IntentKit project.
Checks for invalid imports after upstream package upgrades.
"""

import ast
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import List, Tuple


def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in the given directory."""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip virtual environment and cache directories
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and d not in ["__pycache__", ".venv", "venv"]
        ]

        for file in files:
            if file.endswith(".py"):
                python_files.append(Path(root) / file)

    return python_files


def extract_imports(file_path: Path) -> List[Tuple[str, int]]:
    """Extract all import statements from a Python file."""
    imports = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append((node.module, node.lineno))
                    # Also check individual imports from the module
                    for alias in node.names:
                        if alias.name != "*":
                            full_import = f"{node.module}.{alias.name}"
                            imports.append((full_import, node.lineno))

    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Error parsing {file_path}: {e}")

    return imports


def validate_import(import_name: str) -> bool:
    """Validate if an import is available."""
    try:
        # Handle relative imports
        if import_name.startswith("."):
            return True  # Skip relative imports for now

        # Split the import to get the top-level module
        top_level = import_name.split(".")[0]

        # Try to find the module spec
        spec = importlib.util.find_spec(top_level)
        if spec is None:
            return False

        # For submodules, try to import the full path
        if "." in import_name:
            try:
                importlib.import_module(import_name)
            except (ImportError, AttributeError, ModuleNotFoundError):
                return False

        return True

    except Exception:
        return False


def check_imports_in_file(file_path: Path) -> List[Tuple[str, int]]:
    """Check all imports in a file and return invalid ones."""
    imports = extract_imports(file_path)
    invalid_imports = []

    for import_name, line_no in imports:
        if not validate_import(import_name):
            invalid_imports.append((import_name, line_no))

    return invalid_imports


def main():
    """Main function to check imports in the IntentKit project."""
    try:
        project_root = Path(__file__).parent.parent
        intentkit_dir = project_root / "intentkit"

        print(f"Script location: {Path(__file__)}")
        print(f"Project root: {project_root}")
        print(f"IntentKit directory: {intentkit_dir}")

        if not intentkit_dir.exists():
            print(f"IntentKit directory not found: {intentkit_dir}")
            sys.exit(1)

        print("Checking imports in IntentKit project...")
        print(f"Checking directory: {intentkit_dir}")
        print("-" * 50)
    except Exception as e:
        print(f"Error in main setup: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    python_files = find_python_files(intentkit_dir)
    total_files = len(python_files)
    files_with_issues = 0
    total_invalid_imports = 0

    for file_path in python_files:
        invalid_imports = check_imports_in_file(file_path)

        if invalid_imports:
            files_with_issues += 1
            total_invalid_imports += len(invalid_imports)

            relative_path = file_path.relative_to(project_root)
            print(f"\n❌ {relative_path}")

            for import_name, line_no in invalid_imports:
                print(f"   Line {line_no}: {import_name}")

    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Total files checked: {total_files}")
    print(f"  Files with invalid imports: {files_with_issues}")
    print(f"  Total invalid imports: {total_invalid_imports}")

    if files_with_issues == 0:
        print("✅ All imports are valid!")
        sys.exit(0)
    else:
        print("❌ Found invalid imports that need attention.")
        sys.exit(1)


if __name__ == "__main__":
    main()
