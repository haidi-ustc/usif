# Upgrading USIF 0.8 files

USIF 0.9.0 writes `.usif` record format 7 and SQLite `.usifc` datasets. Files written by USIF 0.8 and earlier (format-5/6 records and version-2 containers) are still readable through the frozen readers in `usif.upgrade`. Their layout is specified in [FORMATS_0_8.md](../FORMATS_0_8.md). [`examples/04_upgrade_0_8_files.py`](../../examples/04_upgrade_0_8_files.py) is a working script; the snippets below use the fixtures in `tests/fixtures/` and run from the repository root.

For the code changes (0.8 API -> 0.9 API), see the migration guide in the 0.9.0 entry of [CHANGELOG.md](../CHANGELOG.md).

## Records (`.usif`, format 5/6)

`usif.read` detects format-5/6 records and decodes them; the stored SHA-256 geometry hash is recomputed and checked.

```python
import usif

old = usif.read("tests/fixtures/format5/rutile_136.usif")
print(old, old.properties.units())
usif.write(old, "rutile.usif")            # rewrite as format 7
```

`usif.decode()` reads only format 7. For bytes rather than files, use `usif.upgrade.format6.decode(data)`; `usif.upgrade.is_format6(data)` tells the two apart.

Symmetric format-5/6 records are expanded to all atoms. The 0.8 atom order of expanded records (sorted by atomic number, then coordinates) is kept as it was decoded.

## Containers (`.usifc`, version 2)

A version-2 container is not an SQLite file; `usif.Dataset` cannot open it. Import it into a new or existing dataset with `Dataset.import_v2` (open the target with `symmetry="auto"` for compact records):

```python
from usif import Dataset

with Dataset("new.usifc", "w") as ds:
    count = ds.import_v2("tests/fixtures/format6/container_v2.usifc", group="/")
    print(count, ds.groups())
```

`import_v2` keeps groups (recreated below `group`), entry names and entry attributes, copies group attributes, decodes every record (verifying its geometry hash) and stores it as format 7. It runs in one transaction.

If a built-in per-atom property (such as `charge`) is present on only some atoms of a 0.8 record, the missing values are stored as 0, a boolean mask `<name>_present` is added to `arrays`, and a warning is issued.

To read a container without converting it:

```python
from usif.upgrade import is_container_v2, open_container_v2
from usif.upgrade.format6 import decode

path = "tests/fixtures/format6/container_v2.usifc"
print(is_container_v2(path))
with open_container_v2(path) as container:
    for entry in container:
        structure = decode(container.record_bytes(entry.record_hash))
        print(entry.group, entry.name, structure.reduced_formula)
```

## Command line

There is no `usif upgrade` command (it was removed in 0.12.0). Every command reads format-5/6
records, so `usif convert` rewrites one as format 7; a container is converted from Python with
`Dataset.import_v2` as shown above (`usif dataset import` scans structure files and does not read
containers).

```bash
usif convert old.usif new.usif    # a format-5/6 record -> format 7
usif inspect old.usifc            # reports a v2 container and how to import it
```
