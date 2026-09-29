#!/usr/bin/env python3
"""
Environment Validation Script (make check-env)
Validates:
1. Dockerfile pins python:3.11-slim
2. pyproject.toml pins requires-python = ">=3.11,<3.12"
3. Runtime python version check (flags if outside 3.11 in strict containerized builds)
"""
import sys
import re
from pathlib import Path

# Enable utf-8 printing safely on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def check_dockerfiles():
    root = Path(__file__).resolve().parent.parent
    dockerfiles = list(root.glob("**/Dockerfile*"))
    assert len(dockerfiles) > 0, "No Dockerfiles found!"
    
    for df in dockerfiles:
        content = df.read_text(encoding="utf-8")
        if "FROM" in content and "python" in content:
            assert re.search(r"FROM\s+python:3\.11-slim", content), (
                f"Violation in {df}: Dockerfile must pin python:3.11-slim!"
            )
    print("[OK] Dockerfiles verified: Strictly pinned to python:3.11-slim.")

def check_pyproject():
    root = Path(__file__).resolve().parent.parent
    pyproject = root / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml not found!"
    content = pyproject.read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11,<3.12"' in content, (
        "pyproject.toml must specify requires-python = '>=3.11,<3.12'!"
    )
    print("[OK] pyproject.toml verified: requires-python = '>=3.11,<3.12'.")

def check_runtime_version():
    major, minor = sys.version_info.major, sys.version_info.minor
    print(f"[INFO] Current Runtime Python: {sys.version.split()[0]}")
    if (major, minor) != (3, 11):
        print(f"[NOTICE] Host runtime is {major}.{minor}. Docker builds pin python:3.11-slim to ensure wheel compatibility.")
    else:
        print("[OK] Runtime Python is exactly 3.11.")

if __name__ == "__main__":
    try:
        check_dockerfiles()
        check_pyproject()
        check_runtime_version()
        print("[SUCCESS] Environment validation passed successfully.")
        sys.exit(0)
    except AssertionError as e:
        print(f"[FAIL] Environment check failed: {e}", file=sys.stderr)
        sys.exit(1)
