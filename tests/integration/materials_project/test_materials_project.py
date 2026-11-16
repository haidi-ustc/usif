"""Materials Project documents -> structures -> datasets, using the bundled fixtures."""

import io as stdio
import json
import os
import zipfile
from pathlib import Path

import pytest

from scripts.materials_project import (
    convert_mp_to_usif,
    load_mp_data_from_archive,
    load_mp_group,
    safe_extract,
    structure_from_dict,
)
from usif.dataset import Dataset, Q
from usif.errors import ValidationError

DATA = Path(os.environ.get("MP_DATA_DIR", "tests/fixtures/mp_structures"))


def documents():
    pytest.importorskip("monty")
    files = sorted(DATA.glob("group_*/materials.json"))
    if not files:
        pytest.skip(f"no Materials Project data in {DATA}")
    return [doc for path in files for doc in load_mp_group(path)]


def test_documents_convert_with_queryable_fields(tmp_path):
    docs = documents()
    with Dataset(tmp_path / "mp.usifc") as dataset:
        count = dataset.add_many(
            (convert_mp_to_usif(doc) for doc in docs),
            "/mp",
            names=[str(doc["material_id"]) for doc in docs],
        )
        assert count == len(docs) == len(dataset)
        assert dataset.check(full=True).ok
        first = dataset[f"/mp/{docs[0]['material_id']}"]
        assert first.properties.unit("band_gap") == "eV"
        assert first.properties["material_id"] == str(docs[0]["material_id"])
        # The fixtures were downloaded without uncorrected_energy_per_atom, so there is
        # no raw DFT total; MP's corrected energy_per_atom is kept as it is.
        assert "energy" not in first.properties
        assert first.properties["energy_per_atom"] == docs[0]["energy_per_atom"]
        gaps = [doc["band_gap"] for doc in docs]
        assert dataset.count(Q.prop("band_gap") > 0.5) == sum(g > 0.5 for g in gaps)


def test_structure_dicts_need_no_pymatgen():
    document = {
        "lattice": {"matrix": [[4, 0, 0], [0, 4, 0], [0, 0, 4]]},
        "sites": [
            {
                "species": [{"element": "Fe", "occu": 1, "oxidation_state": 2}],
                "abc": [0, 0, 0],
                "properties": {"magmom": 2.0},
            },
            {
                "species": [{"element": "O", "occu": 1, "oxidation_state": -2}],
                "abc": [0.5, 0.5, 0.5],
                "properties": {"magmom": 0.0},
            },
        ],
    }
    doc = {
        "structure": document,
        "band_gap": 1.5,
        "material_id": "mp-1",
        "energy_per_atom": -4.5,  # includes MP2020 corrections
        "uncorrected_energy_per_atom": -4.0,
    }
    structure = convert_mp_to_usif(doc)
    assert structure.properties["energy"] == -8.0  # raw DFT total of the 2-atom cell
    assert structure.properties.unit("energy") == "eV"
    assert structure.properties["energy_per_atom"] == -4.5
    assert structure.reduced_formula == "FeO"
    assert structure.arrays["oxidation_state"].tolist() == [2.0, -2.0]
    assert structure.arrays["magmom"].tolist() == [2.0, 0.0]
    assert structure.properties["band_gap"] == 1.5
    disordered = json.loads(json.dumps(document))
    disordered["sites"][0]["species"][0]["occu"] = 0.5
    with pytest.raises(ValidationError, match="disordered"):
        structure_from_dict(disordered)
    with pytest.raises(ValidationError):
        convert_mp_to_usif({"band_gap": 1.0})


def test_archive_round_trip_and_zip_safety(tmp_path):
    documents()
    archive = tmp_path / "mp.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in DATA.rglob("*.json"):
            zf.write(path, path.relative_to(DATA))
    target = load_mp_data_from_archive(archive, tmp_path / "out")
    assert sorted(p.name for p in target.iterdir())
    evil = stdio.BytesIO()
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "x")
    with zipfile.ZipFile(evil) as zf, pytest.raises(ValueError, match="outside"):
        safe_extract(zf, tmp_path / "safe")


def test_scripts_command_line(tmp_path, capsys):
    documents()
    from typer.testing import CliRunner

    from scripts.materials_project.__main__ import app

    runner = CliRunner()
    result = runner.invoke(app, ["build", str(DATA), str(tmp_path / "mp.usifc")])
    assert result.exit_code == 0, result.output
    assert "added" in result.output
    with Dataset(tmp_path / "mp.usifc", "r") as dataset:
        assert len(dataset) > 0 and dataset.groups() == ["/", "/mp"]
    result = runner.invoke(app, ["download"], env={"MP_API_KEY": ""})
    assert result.exit_code != 0 and "MP_API_KEY" in result.output
