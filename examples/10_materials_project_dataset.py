#!/usr/bin/env python3
"""Work with a local Materials Project dataset exported by USIF.

This example is intentionally safe to run without network access. Use `--help`
for CLI usage. Pass a `group_XX/materials.json` path to load documents and
convert the first entry to `USIFStructure`.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load a local Materials Project group JSON file.")
    parser.add_argument("group_json", nargs="?", help="Path such as mp_dataset/group_01/materials.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.group_json:
        print("Materials Project local dataset example")
        print("Pass a group JSON path, for example: group_01/materials.json")
        print("Use examples/download_mp_data.py to create grouped datasets.")
        return 0

    from usif.integrations.materials_project import convert_mp_to_usif, load_mp_group

    path = Path(args.group_json)
    docs = load_mp_group(path)
    print(f"Loaded MP documents: {len(docs)}")
    if docs:
        structure = convert_mp_to_usif(docs[0])
        print(f"First formula: {structure.formula}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
