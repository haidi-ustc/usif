# USIF examples

Run examples from the repository root with an editable install or with the repository on `PYTHONPATH`.

| File | Purpose |
|---|---|
| `quickstart.py` | Smallest pymatgen -> USIF -> `.usif` -> USIF workflow. |
| `01_manual_structure_binary_roundtrip.py` | Manual `USIFStructure` creation and binary encode/decode. |
| `02_container_write_query_validate.py` | `.usifc` write, query, validation, and stats workflow. |
| `03_pymatgen_conversion_roundtrip.py` | pymatgen conversion through services and adapters. |
| `04_properties_and_hashes.py` | Per-atom properties plus geometry/record hash semantics. |
| `05_symmetry_policy_import.py` | SymmetryPolicy import behavior. |
| `06_json_structure_roundtrip.py` | Official `.json` / `.usif.json` save-load workflow. |
| `07_property_management.py` | Scalar, vector, tensor, and custom property management. |
| `08_property_units.py` | Property unit metadata and Unicode/ASCII unit alias normalization. |
| `download_mp_data.py` | Optional live Materials Project downloader CLI. |

The Materials Project downloader requires the `mp` extra and an API key. Its `--help` command does not require either.
