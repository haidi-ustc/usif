# Public API

This is the public API of USIF 0.12.0. Everything else (for example `usif.codec.wire`, `usif.codec.columns`, `usif.dataset.sql`, `usif.symmetry.spacegroup`, `usif.fileio`, and names starting with `_`) is internal. See [API stability](../API_STABILITY.md).

## `usif`

`Dataset` and `Q` are imported lazily on first access.

| Name | Kind | Description |
|---|---|---|
| `Structure` | class | Atoms, positions, optional cell, `arrays`, `properties` |
| `Cell` | class | Immutable lattice matrix and pbc flags |
| `Schema`, `PropertySpec`, `DEFAULT_SCHEMA` | class, class, instance | Property specs (see [Properties and units](properties.md)) |
| `read(source, *, format=None, backend=None, schema=DEFAULT_SCHEMA)` | function | One structure from a file or a library object |
| `read_all(source, *, format=None, backend=None, schema=DEFAULT_SCHEMA)` | function | Every frame in a file, as a list |
| `write(structure, path, *, format=None, backend=None, **options)` | function | Write one structure; `.usif` takes the `encode` options, `.json` takes `indent` |
| `write_all(structures, path, *, format=None, backend=None)` | function | Several structures to one backend file (e.g. multi-frame XYZ) |
| `convert(obj, to=None, *, schema=DEFAULT_SCHEMA)` | function | Library object -> `Structure`; with `to`, -> that backend's object |
| `encode(structure, **options)` | function | Format-7 record bytes (`compression`, `level`, `precision`, `symmetry`) |
| `decode(data, *, schema=DEFAULT_SCHEMA, max_size=2 GiB)` | function | `Structure` from format-7 record bytes |
| `Dataset`, `Q` | classes | `.usifc` datasets and query conditions |
| `USIFError`, `ValidationError`, `FormatError`, `ChecksumError`, `UnsupportedVersionError`, `DatasetError`, `MissingDependencyError` | exceptions | See [Errors](#errors) |
| `__version__`, `FORMAT_VERSION`, `DATASET_SCHEMA_VERSION` | constants | Package version, record format (7), dataset schema (1) |

## `usif.model`

`Structure`, `Cell`, `Schema`, `PropertySpec`, `DEFAULT_SCHEMA`, `PropertyMap`, `JSON` (the `"json"` dtype marker), `stress_to_voigt()`, `voigt_to_tensor()`.

`Structure` members: `numbers`, `positions`, `cell`, `pbc`, `schema`, `arrays`, `properties`, `natoms`, `len()`, `is_periodic`, `frac_positions`, `volume`, `symbols`, `element_counts`, `formula`, `reduced_formula`, `chemical_system`, `from_fractional()`, `copy()`, `replace()`, `permute()`, `allclose()`, `==`.

`PropertyMap` members: mapping interface plus `set()`, `set_unit()`, `update_from()`, `unit()`, `units()`, `dtype()`, `raw()`, `length`, `copy()`, `subset()`, `allclose()`.

## `usif.codec`

| Name | Description |
|---|---|
| `encode`, `decode` | As in `usif` |
| `encode_with_info(structure, **options)` | `(bytes, RecordInfo)` |
| `decode_with_info(data, *, schema, max_size)` | `(Structure, RecordInfo)` |
| `RecordInfo` | `record_hash`, `geometry_hash`, `natoms`, `compression`, `raw_size`, `stored_size`, `symmetric` |
| `is_record(data)`, `read_header(data)`, `RecordHeader` | Header inspection without decoding |
| `FORMAT_VERSION` | 7 |
| `usif.codec.jsondoc` | `dumps(structure, *, indent=2)`, `loads(text, *, schema)`, `to_document()`, `from_document()`, `SCHEMA_ID` (`"usif.structure.json.v2"`) |
| `usif.codec.compression` | `Compressor`, `register()`, `get()`, `available()`; built-in codecs `none` (0), `zlib` (1), `lzma` (2), `zstd` (3); ids 0-63 are reserved for USIF |

See [Records and JSON documents](records.md).

## `usif.dataset`

| Name | Description |
|---|---|
| `Dataset(path, mode="a", *, compression="zlib", level=None, precision="f64", symmetry="off", schema=DEFAULT_SCHEMA, timeout=30.0)` | Methods: `add`, `add_many`, `add_record`, `link`, `remove`, `set_attrs`, `set_group_attrs`, `import_v2`, `transaction`, `get`, `[]`, `entry`, `in`, `query`, `structures`, `count`, `len`, `iter`, `groups`, `group_attrs`, `metadata`, `stats`, `check`, `compact`, `close`; context manager |
| `Entry` | `id`, `group`, `name`, `path`, `record_hash`, `attrs`, `structure` |
| `CheckReport` | `ok`, `errors`, `checked_records` |
| `Q` | `all`, `formula`, `chemsys`, `elements`, `natoms`, `periodic`, `geometry`, `record`, `has_prop`, `prop`, `group`, `name`, `has_attr`, `attr`; `prop()` and `attr()` take comparisons and `.between(low, high)`; combine with `&`, `\|`, `~` |

See [Datasets](datasets.md).

## `usif.agent`

The data agent and local-dataset import ([guide](agent.md)). Nothing here is imported by `import usif`.

| Name | Description |
|---|---|
| `scan(root, *, group="/", dataset=None, all_frames=False)` | Find calculations and structure files -> `ScanResult` (`candidates`, `new`, `skipped`) of `Candidate`s (`path`, `source`, `sha256`, `formula`, `natoms`, `properties`, `attrs`, `status`) |
| `Plan(dataset, operations, options, origin, request)` | A change plan (JSON `usif.agent.plan.v2`; earlier plan formats are refused): `id`, `describe()`, `to_dict()`, `save(path)`, `Plan.load(path)`, `Plan.from_dict(data)` |
| `Operation(op, target, attrs, source, sha256, frame, overwrite, note)` | One change: `add`, `link`, `set_attrs`, `set_group_attrs` or `remove` |
| `plan_from_scan(dataset, candidates, *, update=False, options=None)` | A plan adding the new candidates |
| `apply_plan(plan, *, dataset=None) -> ApplyReport` | Verify and apply an approved plan in one transaction |
| `LLMConfig`, `load_config(overrides=None)` | OpenAI-compatible endpoint settings (DeepSeek by default) |
| `usif.agent.config.default_dataset()`, `agent_dataset(explicit=None)` | The explicitly configured default dataset (`USIF_DATASET`, then `[agent] dataset`) and where it is set; the dataset `ask`/`chat` use |
| `ChatClient(config)`, `ChatModel` | The HTTP chat client and the protocol it implements (`complete(messages, tools)`) |
| `Toolbox(dataset, *, roots=())` | The agent's read-only and `propose_*` tools (including projects: `list_projects`, `propose_project`, `propose_link`); `plan` holds the proposals |
| `Session(model, toolbox, *, on_tool=None)` | The conversation loop: `ask(text) -> str`, `plan` |

## `usif.backends`

`Backend` and `FileBackend` (protocols), `register(backend, *, replace=False)`, `get(name)`, `backends()`, `available(name)`, `for_object(obj)`, `is_instance_of(obj, package, *qualnames)`. Built-in backend classes: `usif.backends.matsimpy.MatsimpyBackend`, `usif.backends.ase.AseBackend`, `usif.backends.pymatgen.PymatgenBackend`. Plugins use the entry-point group `usif.backends`. See [Writing a backend](libraries.md#writing-a-backend).

## `usif.upgrade`

Frozen, read-only readers for files written by USIF 0.8 and earlier:

- `is_format6(data)`, `Format6Info`, and in `usif.upgrade.format6`: `decode(data, *, schema)`, `decode_with_info(data, *, schema)`;
- `is_container_v2(path)`, `open_container_v2(path)` (a context manager yielding a `V2Container`: iterate `V2Entry` items with `group`, `name`, `record_hash`, `attrs`; `len()`; `record_bytes(hash)`; `group_attrs`; `close()`).

See [Upgrading USIF 0.8 files](upgrading.md).

## `usif.symmetry`

`analyze(structure, symprec=1e-3) -> SpacegroupInfo` (`number`, `symbol`, `hall_number`, `wyckoffs`, `equivalent_atoms`) for 3D-periodic structures. `reduce()`, `expand()`, `SymmetricForm` and `LOSSLESS_TOLERANCE` (1e-5 Å) implement `symmetry="auto"` record storage.

## Other modules

| Module | Public names |
|---|---|
| `usif.units` | `normalize_unit(unit)`, `convert(value, from_unit, to_unit)`, `EV_PER_ANG3_IN_GPA` |
| `usif.errors` | the exception classes |
| `usif.version` | `__version__`, `FORMAT_VERSION`, `DATASET_SCHEMA_VERSION`, `RELEASE_DATE`, `RELEASE_SEQUENCE`, `RELEASE_RECORD`, `RELEASE_ID`, `VERSION_INFO`, `VERSION_MAJOR`, `VERSION_MINOR`, `VERSION_PATCH` |
| `usif.cli` | `main(argv=None) -> int`; the `usif` console script |

## Errors

```text
USIFError
├── ValidationError (ValueError)          invalid model input or arguments
├── FormatError (ValueError)              malformed or unsupported bytes or documents
│   ├── ChecksumError                     stored digest does not match the payload
│   └── UnsupportedVersionError           record or dataset version this reader cannot read
├── DatasetError                          dataset cannot be opened, written or queried
├── AgentError                            LLM service, agent configuration or change plan problem
└── MissingDependencyError (ImportError)  optional package not installed
```
