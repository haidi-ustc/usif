"""Engineering workflow and release-layout guardrails."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


TEST_LAYERS = {
    "unit",
    "integration",
    "reliability",
    "examples",
    "fixtures",
}


REQUIRED_MARKERS = {
    "unit",
    "integration",
    "interop",
    "mp_data",
    "network",
    "slow",
    "reliability",
    "examples",
}


def test_test_suite_uses_layered_directory_layout():
    root = Path("tests")
    assert TEST_LAYERS.issubset({path.name for path in root.iterdir() if path.is_dir()})
    assert not list(root.glob("test_*.py"))
    assert (root / "conftest.py").exists()


def test_pytest_markers_are_registered_in_pyproject():
    text = Path("pyproject.toml").read_text()
    for marker in REQUIRED_MARKERS:
        assert f'"{marker}:' in text
    assert (
        'testpaths = ["tests/unit", "tests/integration", "tests/reliability", "tests/examples"]'
        in text
    )


def test_ci_workflow_covers_quality_test_and_build_smoke():
    workflow = Path(".github/workflows/ci.yml")
    assert workflow.exists()
    text = workflow.read_text()
    for expected in (
        "black --check",
        "isort --check-only",
        "mypy usif",
        "bandit -q -r usif",
        "pip_audit",
        "python scripts/check_release_metadata.py",
        "pytest tests/unit",
        "pytest tests/integration tests/reliability tests/examples",
        "python -m build",
        "dist/*.whl",
    ):
        assert expected in text


def test_release_artifact_hygiene_files_are_configured():
    assert not Path("setup.cfg").exists()
    manifest = Path("MANIFEST.in").read_text()
    for excluded in ("docs/archive", ".pytest_cache", "build", "dist", "*.egg-info"):
        assert excluded in manifest
    assert "docs/RELEASE.md" in manifest
    assert "docs/TESTING.md" in manifest
    assert "docs/API_STABILITY.md" in manifest
    assert "docs/FORMAT_VERSIONING.md" in manifest
    assert "recursive-include scripts *.py" in manifest
    assert "recursive-include docs/site *.md" in manifest


def test_release_governance_docs_and_script_exist():
    assert Path("scripts/check_release_metadata.py").exists()
    for doc in ("docs/API_STABILITY.md", "docs/FORMAT_VERSIONING.md"):
        assert Path(doc).exists()
    api = Path("docs/API_STABILITY.md").read_text()
    fmt = Path("docs/FORMAT_VERSIONING.md").read_text()
    assert "Public API" in api
    assert "Internal API" in api
    assert "FORMAT_VERSION = 5" in fmt
    release_record = tomllib.loads(Path("pyproject.toml").read_text())["tool"]["usif"]["release"]["record"]
    assert release_record in fmt
    assert "python scripts/check_release_metadata.py" in fmt


def test_core_docs_match_current_6_5_code_boundaries():
    docs = {
        name: Path(f"docs/{name}").read_text()
        for name in (
            "ARCHITECTURE.md",
            "BINARY_FORMAT.md",
            "CONTAINER_FORMAT.md",
            "PROPERTY_SYSTEM.md",
        )
    }

    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    project_version = pyproject["project"]["version"]
    release_record = pyproject["tool"]["usif"]["release"]["record"]

    architecture = docs["ARCHITECTURE.md"]
    for expected in (
        f"USIF {project_version} architecture",
        "USIFStructure is a pure model",
        "RecordStore",
        "ContainerIndexStore",
        "usif.integrations.materials_project",
        release_record,
        "official USIF JSON",
        "interop common protocols",
        "ASE adapter depends on pymatgen",
        "scripts/check_release_metadata.py",
        "docs/site",
    ):
        assert expected in architecture

    binary = docs["BINARY_FORMAT.md"]
    for expected in (
        "Binary record format version | `5`",
        "`b\"USIF\\x00\\x00\\x00\"`",
        "geometry_hash",
        "0 = NONE",
        "1 = GZIP",
        "structure_property_section_length",
    ):
        assert expected in binary
    assert "Format Version**: 4" not in binary
    assert "LZMA" not in binary

    container = docs["CONTAINER_FORMAT.md"]
    for expected in (
        "`b\"USIFC\\x00\\x00\"`",
        "`b\"USIFIDX1\"`",
        "`b\"USIFDONE\"`",
        "record_hash",
        "geometry_hash",
        "ContainerIndexStore.find_latest_valid_index_offset",
    ):
        assert expected in container

    properties = docs["PROPERTY_SYSTEM.md"]
    for expected in (
        "PropertyRegistry.with_builtins()",
        "DEFAULT_REGISTRY",
        "create_default_registry()",
        "force",
        "energy",
        "__USIF_JSON__:",
        "SymmetryPolicy",
        "usif.structure.json.v1",
        "set_tensor",
        "Unit metadata",
        "Ang^2",
    ):
        assert expected in properties


def test_documentation_site_is_productized_and_packaged():
    site = Path("docs/site")
    required = (
        "index.md",
        "quickstart.md",
        "concepts/structure-model.md",
        "concepts/properties-and-units.md",
        "concepts/binary-format.md",
        "concepts/container-format.md",
        "tutorials/README.md",
        "tutorials/container-workflow.md",
        "tutorials/materials-project.md",
        "cookbook/README.md",
        "api/public-api.md",
    )
    for relative in required:
        assert (site / relative).exists()
    index = (site / "index.md").read_text()
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    assert pyproject["project"]["version"] in index
    assert pyproject["tool"]["usif"]["release"]["record"] in index
    assert "USIFStructure is a pure model" in index
    assert "docs/site" in Path("README.md").read_text()


def test_mypy_no_longer_ignores_interop_adapters():
    pyproject = Path("pyproject.toml").read_text()
    assert 'module = ["usif.interop.*"]' not in pyproject
    assert "ignore_errors = true" not in pyproject.split("[tool.bandit]")[0]


def test_interop_common_contract_modules_exist():
    for path in (
        Path("usif/interop/common/protocols.py"),
        Path("usif/interop/common/type_guards.py"),
    ):
        assert path.exists()
    architecture = Path("docs/ARCHITECTURE.md").read_text()
    assert "interop common protocols" in architecture
    assert "ASE adapter depends on pymatgen" in architecture


def test_examples_use_clear_descriptive_filenames():
    example_names = {path.name for path in Path("examples").glob("*.py")}
    assert "example-1.py" not in example_names
    assert "example-2.py" not in example_names
    for expected in (
        "01_manual_structure_binary_roundtrip.py",
        "02_container_write_query_validate.py",
        "03_pymatgen_conversion_roundtrip.py",
        "04_properties_and_hashes.py",
        "05_symmetry_policy_import.py",
        "06_json_structure_roundtrip.py",
        "07_property_management.py",
        "08_property_units.py",
        "09_large_container_workflow.py",
        "10_materials_project_dataset.py",
        "download_mp_data.py",
        "quickstart.py",
    ):
        assert expected in example_names


def test_example_docs_match_current_json_and_mp_workflows():
    examples_readme = Path("examples/README.md").read_text()
    mp_readme = Path("examples/README_MP_DOWNLOAD.md").read_text()

    assert "06_json_structure_roundtrip.py" in examples_readme
    assert "07_property_management.py" in examples_readme
    assert "08_property_units.py" in examples_readme
    assert "09_large_container_workflow.py" in examples_readme
    assert "10_materials_project_dataset.py" in examples_readme
    assert "Official `.json` / `.usif.json`" in examples_readme
    assert "group_01/materials.json" in mp_readme
    assert "load_mp_group" in mp_readme
    assert "convert_mp_to_usif" in mp_readme
    assert "mp-12345.json" not in mp_readme
    assert "examples.download_mp_data.load_structure" not in mp_readme


def test_library_property_modules_do_not_contain_demo_main_blocks():
    for path in (
        Path("usif/properties/definitions.py"),
        Path("usif/properties/structure.py"),
    ):
        assert 'if __name__ == "__main__"' not in path.read_text()
