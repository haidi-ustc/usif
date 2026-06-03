#!/usr/bin/env python3
"""Compatibility wrapper for the canonical pytest test runner."""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run the project test suite with pytest."""
    cmd = [sys.executable, "-m", "pytest"]
    return subprocess.run(cmd, cwd=Path(__file__).parent).returncode


if __name__ == "__main__":
    sys.exit(main())
