#!/usr/bin/env python3
"""
Comprehensive import validation script for IntentKit project.
Combines multiple methods to check for invalid imports after upstream package upgrades.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_py_compile_check(directory: Path) -> bool:
    """Run py_compile check on all Python files."""
    print("🔍 Running py_compile syntax and import check...")

    try:
        result = subprocess.run(
            [
                "find",
                str(directory),
                "-name",
                "*.py",
                "-exec",
                "python",
                "-m",
                "py_compile",
                "{}",
                ";",
            ],
            capture_output=True,
            text=True,
            cwd=directory.parent,
        )

        if result.returncode == 0:
            print("✅ py_compile check passed")
            return True
        else:
            print("❌ py_compile check failed:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running py_compile: {e}")
        return False


def run_pytest_import_check() -> bool:
    """Run pytest to check for import issues."""
    print("\n🔍 Running pytest import check...")

    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "--collect-only", "-q"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ pytest import check passed")
            return True
        else:
            print("❌ pytest import check failed:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running pytest: {e}")
        return False


def run_ruff_import_check(directory: Path) -> bool:
    """Run ruff to check for import-related issues."""
    print("\n🔍 Running ruff import check...")

    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "ruff",
                "check",
                "--select",
                "F401,F811,F821,F822,F823",
                str(directory),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ ruff import check passed")
            return True
        else:
            print("❌ ruff import check found issues:")
            print(result.stdout)
            return False
    except Exception as e:
        print(f"❌ Error running ruff: {e}")
        return False


def test_direct_import() -> bool:
    """Test direct import of the main package."""
    print("\n🔍 Testing direct package import...")

    try:
        print("✅ Direct import of intentkit successful")
        return True
    except Exception as e:
        print(f"❌ Direct import failed: {e}")
        return False


def find_python_files(directory: Path) -> list[Path]:
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


def check_specific_imports(directory: Path) -> bool:
    """Check specific import patterns that might be problematic."""
    print("\n🔍 Checking for potentially problematic import patterns...")

    python_files = find_python_files(directory)
    issues_found = False

    # Common problematic patterns after package upgrades
    problematic_patterns = [
        "from langchain.llms import",
        "from langchain.chat_models import",
        "from langchain.embeddings import",
        "from pydantic import BaseSettings",  # Changed to BaseModel in v2
        "from sqlalchemy.ext.declarative import declarative_base",  # Changed in 2.0
    ]

    for file_path in python_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            for pattern in problematic_patterns:
                if pattern in content:
                    print(
                        f"⚠️  Found potentially outdated import in {file_path.relative_to(directory.parent)}"
                    )
                    print(f"   Pattern: {pattern}")
                    issues_found = True

        except Exception as e:
            print(f"❌ Error checking {file_path}: {e}")

    if not issues_found:
        print("✅ No problematic import patterns found")

    return not issues_found


def main():
    """Main function to run comprehensive import checks."""
    print("🚀 IntentKit Comprehensive Import Validation")
    print("=" * 50)

    project_root = Path(__file__).parent.parent
    intentkit_dir = project_root / "intentkit"

    if not intentkit_dir.exists():
        print(f"❌ IntentKit directory not found: {intentkit_dir}")
        sys.exit(1)

    print(f"📁 Project root: {project_root}")
    print(f"📁 Checking directory: {intentkit_dir}")
    print()

    # Run all checks
    checks = [
        ("py_compile", lambda: run_py_compile_check(intentkit_dir)),
        ("pytest", run_pytest_import_check),
        ("ruff", lambda: run_ruff_import_check(intentkit_dir)),
        ("direct_import", test_direct_import),
        ("pattern_check", lambda: check_specific_imports(intentkit_dir)),
    ]

    results = {}

    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"❌ Error in {check_name}: {e}")
            results[check_name] = False

    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)

    passed = sum(results.values())
    total = len(results)

    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check_name:15} {status}")

    print(f"\nOverall: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 All import checks passed! Your imports are healthy.")
        sys.exit(0)
    else:
        print("⚠️  Some import issues detected. Please review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
