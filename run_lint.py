#!/usr/bin/env python3
"""Run canonical local lint checks for USIF."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
CHECK_PATHS = ["usif", "tests", "examples"]

def run_command(cmd, description):
    print(f"\n{'=' * 70}")
    print(f"Running {description}...")
    result = subprocess.run(cmd, cwd=ROOT)
    print("passed" if result.returncode == 0 else "failed")
    return result.returncode == 0

def require_tools(tools):
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        print("Missing required lint tools:", ", ".join(missing))
        print('Install them with: python -m pip install -e ".[dev]"')
        sys.exit(1)

def main() -> int:
    parser = argparse.ArgumentParser(description="Run USIF lint checks")
    parser.add_argument("--fix", action="store_true", help="Apply black and isort formatting.")
    parser.add_argument("--check-black", action="store_true", help="Also run black --check.")
    args = parser.parse_args()
    tools = ["isort", "flake8"] + (["black"] if args.fix or args.check_black else [])
    require_tools(tools)
    commands = []
    if args.fix:
        commands.extend([(["black", *CHECK_PATHS], "black formatter"), (["isort", *CHECK_PATHS], "isort formatter")])
    else:
        if args.check_black:
            commands.append((["black", "--check", *CHECK_PATHS], "black formatting check"))
        commands.append((["isort", "--check-only", "--diff", *CHECK_PATHS], "isort import sorting check"))
    commands.append((["flake8", *CHECK_PATHS], "flake8 code style check"))
    return 0 if all(run_command(*item) for item in commands) else 1

if __name__ == "__main__":
    sys.exit(main())
