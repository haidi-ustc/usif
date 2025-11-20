#!/usr/bin/env python3
"""
Run linting checks (flake8 and isort) for USIF project
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*70}")
    print(f"Running {description}...")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=Path(__file__).parent)

    if result.returncode == 0:
        print(f"\n✓ {description} passed!")
        return True
    else:
        print(f"\n✗ {description} failed!")
        return False


def main():
    """Run all linting checks"""
    print("=" * 70)
    print("USIF Linting Checks")
    print("=" * 70)

    # Check if tools are installed
    try:
        subprocess.run(["flake8", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n✗ flake8 is not installed!")
        print("Install it with: pip install flake8")
        sys.exit(1)

    try:
        subprocess.run(["isort", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n✗ isort is not installed!")
        print("Install it with: pip install isort")
        sys.exit(1)

    # Run isort check
    isort_check = run_command(
        ["isort", "--check-only", "--diff", "usif", "tests", "examples"],
        "isort (import sorting check)",
    )

    # Run flake8
    flake8_check = run_command(
        ["flake8", "usif", "tests", "examples"], "flake8 (code style check)"
    )

    # Summary
    print("\n" + "=" * 70)
    print("Linting Summary")
    print("=" * 70)

    all_passed = isort_check and flake8_check

    if all_passed:
        print("✓ All linting checks passed!")
        sys.exit(0)
    else:
        print("✗ Some linting checks failed!")
        print("\nTo fix issues:")
        print("  - Run 'isort usif tests examples' to fix import order")
        print("  - Fix flake8 errors manually")
        sys.exit(1)


if __name__ == "__main__":
    main()
