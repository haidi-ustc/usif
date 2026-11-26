# Data agent and local datasets

USIF can turn a research group's scattered calculations into one local `.usifc` dataset that keeps
growing and can be searched and reused. Two command-line tools build it:

* `usif dataset import` finds calculations in project directories and registers them. It is
  deterministic and needs no LLM.
* `usif agent` is a language-model assistant. You ask it questions and give it instructions in
  plain words ("which SrTiO3 runs used ENCUT 520?", "register the new calculations in
  ~/projects/oer", "create a project for the OER work and save every Ti oxide with a band gap
  above 1 eV into it"). It uses the dataset tools to answer.

Neither tool writes to the dataset without your approval. Both produce a **change plan** that you
review, and only an approved plan is applied. Everything stays local: the only data that leaves
your machine is what the agent sends to the LLM endpoint you configure.

Examples: [`examples/06_local_dataset.py`](../../examples/06_local_dataset.py) (import and
plans) and [`examples/07_agent_projects.py`](../../examples/07_agent_projects.py) (projects in
plain words, with a scripted model instead of an LLM).

## Importing project directories

```bash
usif dataset import ~/projects/oer group.usifc --group /oer            # review, then confirm
usif dataset import ~/projects/oer group.usifc --group /oer --plan-out oer-plan.json
usif agent apply oer-plan.json                                         # later, after review
```

The scan reads only files it recognises and skips hidden directories. It never follows symbolic
links and opens no file that resolves outside the scanned directory. That includes `INCAR`,
`KPOINTS` and README files, so a link cannot pull an outside file into the dataset.

| Found | Becomes | Structure |
|---|---|---|
| A VASP directory (`vasprun.xml`, `OUTCAR`, `CONTCAR` or `POSCAR`) | one entry named after the directory | final frame of the first file present, in that order |
| `*.usif`, `*.json`, `*.cif`, `*.xyz`, `*.extxyz`, `*.traj`, `*.vasp`, `*.poscar`, `*.pdb`, `*.xsf` | one entry named after the file stem | last frame; one entry per frame with `--all-frames` |

Directories become groups below `--group`. For example, with `--group /oer`,
`perovskites/SrTiO3/relax/` becomes the entry `/oer/perovskites/SrTiO3/relax`. Formats other than
`.usif` and `.json` need a backend (`pip install usif[ase]`). Files that cannot be read are listed
and skipped.

Each entry's attributes record where it came from, so results stay traceable and reproducible:

| Attribute | Content |
|---|---|
| `source`, `source_sha256`, `source_bytes`, `source_modified` | absolute path, SHA-256, size and modification time of the file read |
| `source_frame`, `source_frames` | which frame, of how many |
| `code` | `vasp` for VASP directories |
| `incar`, `kpoints` | INCAR parameters (`{"ENCUT": 520, ...}`) and the KPOINTS header |
| `notes` | the nearest `README`/`NOTES` text in the directory or its parents (up to 2000 characters) |
| `plan`, `registered` | the id of the approved plan that added the entry, and when it was applied |

You can query these attributes like any others, for example `Q.attr("code") == "vasp"` or
`Q.attr("plan") == "8e372947aa0d5e2f"`.

Importing is incremental. A file that is already registered (same path, SHA-256 and frame) is
skipped, so running the same import again adds only new calculations. Identical files in two
directories count as two calculations. An entry whose source file has changed is reported as a
conflict, and `--update` replaces such entries.

Two candidates can map to the same entry, for example a VASP directory `calc/` and a file
`calc.cif` next to it. In that case the later one is named after its full file name
(`calc.cif`). Any candidate that still collides is reported as a duplicate and is not imported.

## Change plans and approval

A plan is a JSON file (`usif.agent.plan.v2`) listing operations on one dataset:

| Operation | Effect |
|---|---|
| `add` | store the structure from `source` (verified against `sha256`) as entry `target` |
| `link` | make entry `target` refer to the record of entry `source`: nothing is copied, the attributes are copied and `linked_from` is added |
| `set_attrs` | merge attributes into an entry |
| `set_group_attrs` | merge attributes into a group, such as its description |
| `remove` | remove an entry; its record stays until `usif dataset compact` |

```text
plan 148d5135ac05c74a for /data/group.usifc: 1 add, 1 set_group_attrs
  request: Register any new calculations from the project folder ...
  add       /oer/perovskites/BaTiO3/relax  <-  /home/me/projects/oer/perovskites/BaTiO3/relax/POSCAR
  group     /oer/perovskites  {description}  (the group had no description)
```

* **Approval.** An interactive command shows the plan and asks `Apply these N changes? [y/N]`,
  and the default is no. Without a terminal, or when you answer no, the plan is saved as
  `~/.usif/plans/<id>.json` and nothing is applied. `usif agent apply PLAN --yes` (or `-y`) applies a plan you have reviewed;
  `usif dataset import --yes` applies a scan you started yourself. The agent cannot approve
  anything: `ask` and `chat` have no `--yes`.
* **What you see is what runs.** The review shows every operation with its attribute values.
  Text that can come from the model (notes, paths, attributes, the request) has control characters
  escaped and is shortened, and so does the agent's answer. A crafted answer cannot hide or forge
  lines of the plan. Hand-edited plans are type-checked field by field.
* **Integrity.** The plan id is a hash of the plan format, the dataset path, the encoding
  options and the operations. A plan edited after it was written is refused until you delete its `id` field to
  accept the edits. Before writing, `apply` checks every source file against its SHA-256 and every
  target entry against the dataset. It then applies all operations in one transaction, or none,
and checks each source file's hash again after reading it.
* **Reproducibility.** Added entries carry the plan id, and the command line keeps every applied
  plan in `~/.usif/plans/applied/<id>.json`. Together they record what was added, from which files,
  and why; the `note` of each operation holds the agent's reason. `usif agent plans` lists the
  plans waiting for review, and `usif agent plans --applied` lists the journal.
* **Plan format.** USIF 0.12 reads and writes `usif.agent.plan.v2` only (the operations above).
  Plans saved by 0.10 and 0.11 (`usif.agent.plan.v1`) are not read: `show` and `apply` refuse
  them with a message naming the format, and `usif agent plans` lists them with that message.
  Their files are left as they are, so the journal keeps its record of what was applied (and
  entries keep their `plan` ids); a pending v1 plan has to be made again, for example by
  running the same `usif dataset import` or asking the agent again.

From Python:

```python
from usif.agent import Plan, apply_plan, plan_from_scan, scan

result = scan("projects/oer", group="/oer", dataset="group.usifc")
plan = plan_from_scan("group.usifc", result.candidates)
print(plan.describe())
plan.save("oer-plan.json")
apply_plan(Plan.load("oer-plan.json"))   # after review
```

## Asking the agent

```bash
export DEEPSEEK_API_KEY=...                       # read from the environment only
usif agent ask group.usifc "Which Ti-containing calculations do we have, with ENCUT?"
usif agent ask group.usifc "Register new runs in ~/projects/oer under /oer" --allow ~/projects/oer
usif agent chat group.usifc --allow ~/projects    # interactive; /plan /apply /save FILE /discard /quit
```

### Default dataset

`DATASET` can be left out (`usif agent ask "Which projects do we have?"`, `usif agent chat`)
when a default dataset is configured explicitly. The dataset is, in order of priority:

1. the `DATASET` argument;
2. the `USIF_DATASET` environment variable;
3. `dataset` in the `[agent]` table of `~/.usif/config.toml`:

```toml
# ~/.usif/config.toml
[agent]
dataset = "/data/group/lab.usifc"
```

Nothing else is guessed: with none of the three, the command fails and asks for `DATASET`.
A default must be an absolute path to a `.usifc` file that exists; it is never created. To
start a new dataset, give its path as `DATASET` (an approved plan creates it). `usif agent
config` shows the default in effect and where it comes from. A default changes nothing about
approval: `ask` and `chat` still cannot apply a plan.

### Exports

The agent cannot write files. Asked to export data, it gives you a `usif dataset export`
command with the matching filters (see [Exporting](datasets.md#exporting)), which you run
yourself.

The agent works with these tools:

| Tool | Effect |
|---|---|
| `dataset_overview`, `search_entries`, `get_entry` | read the dataset, opened read-only. Search filters: group, formula, chemical system, elements present or absent, atom count, numeric properties (`energy < -10`), exact attributes, and text in paths, notes and parameters |
| `list_projects` | the projects (`/projects/<name>`) with their descriptions and entry counts |
| `inspect_file`, `scan_directory` | read structure files and scan directories, only inside `--allow` directories (default: the current directory) |
| `propose_project` | create or describe the project `/projects/<name>` |
| `propose_import`, `propose_link` | save scanned files, or entries already in the dataset (listed paths or a search), into a group such as a project |
| `propose_entry_attrs`, `propose_group_attrs`, `propose_remove` | change attributes, remove entries |
| `propose_storage_options` | compression and symmetry of the structures the plan adds (lossless choices only; only when you ask) |
| `show_plan`, `discard_plan` | review or drop the plan |

The agent reports what it proposed. When it finishes, the command prints the plan and asks for
approval as described above. `chat` keeps the plan across turns: `/plan` shows it and `/apply`
asks for approval. On `/quit`, an unapproved plan is saved to a file.

## Projects in plain words

A project is the group `/projects/<name>`; its group attributes describe it. Projects need no
special support in the dataset: an entry belongs to a project when its path is below the project
group, and `Q.group("/projects/oer")` finds them.

```bash
usif agent ask lab.usifc "Create a project 'oer' for our OER perovskite work"
usif agent ask lab.usifc "Save every Ti oxide with a band gap above 1 eV into the oer project"
usif agent ask lab.usifc "Save the runs in ~/runs/srtio3 into project oer" --allow ~/runs
usif agent ask lab.usifc "Which projects do we have? What is in oer below -40 eV?"
```

* **Create.** `propose_project` proposes `set_group_attrs /projects/<name> {description, ...}`.
  The dataset may not exist yet: the approved plan creates it.
* **Save existing entries.** `propose_link` takes entry paths, or the same filters as a search,
  and proposes one `link` per entry (at most 500). A link is a second entry for the same stored
  record, so saving into a project costs no space and the original entry is untouched. The
  entries keep their layout below their common parent group: `/oer/SrTiO3/relax` and
  `/oer/BaTiO3/relax` become `/projects/<name>/SrTiO3/relax` and `.../BaTiO3/relax`. Entries
  already in the project, or saved there before (`linked_from`), are skipped.
* **Save new files.** The agent scans the files with the group `/projects/<name>/...` and proposes
  an import, as above.
* **Query.** `search_entries` and `list_projects` answer questions; nothing is proposed.

Each of these is a plan you approve, as described above. The plan shows the storage options when
the agent set them (`options for added structures: compression=lzma`); the agent cannot choose
the lossy `precision="f32"`. In Python, `Dataset.link(source, name, group)` does the same as a
`link` operation.

## Privacy

The agent sends your questions and the tool results (entry paths, formulas, attributes, file paths)
to the LLM endpoint. It never sends the API key: the key goes only into the HTTP `Authorization`
header and is removed from error messages. Redirects are refused, because urllib would send
the header on to the new address. Plain `http://` endpoints are accepted only on the local
machine (`localhost`, `127.0.0.1`, `::1`). `usif agent config` reports only whether the key is
set.

## The `~/.usif` directory

USIF keeps per-user files in `~/.usif`, or in `$USIF_HOME` if that is set. Nothing is created
until something is saved there.

```text
~/.usif/
  config.toml        [llm] and [agent] settings (below and "Default dataset")
  plans/             change plans waiting for review
  plans/applied/     every plan applied from the command line, by id
```

Datasets live wherever you keep them. Put a group's shared dataset on a local disk of the machine
that writes it (see [datasets](datasets.md#concurrency-and-crashes)).

## LLM configuration

Any OpenAI-compatible `/chat/completions` endpoint with tool calling works. The default is
DeepSeek:

| Setting | Default | Environment | `config.toml` `[llm]` |
|---|---|---|---|
| endpoint | `https://api.deepseek.com` | `USIF_LLM_BASE_URL` | `base_url` |
| model | `deepseek-flash` | `USIF_LLM_MODEL` | `model` |
| variable holding the key | `DEEPSEEK_API_KEY` | `USIF_LLM_API_KEY_ENV` | `api_key_env` |
| temperature | `0.0` | `USIF_LLM_TEMPERATURE` | `temperature` |
| timeout (s) | `120` | `USIF_LLM_TIMEOUT` | `timeout` |

Settings are applied in this order, each overriding the previous one:

1. the defaults;
2. `~/.usif/config.toml`;
3. the environment variables;
4. the `--model` and `--base-url` options.

The configuration file may not contain a key. For example, to use another provider:

```toml
# ~/.usif/config.toml
[llm]
base_url = "https://api.openai.com/v1"
model = "gpt-4.1-mini"
api_key_env = "OPENAI_API_KEY"
```

A local server such as vLLM or Ollama works too (`base_url = "http://localhost:11434/v1"`).
`usif agent config` shows the settings in effect, including the default dataset.
