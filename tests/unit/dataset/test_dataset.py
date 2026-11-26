"""SQLite-backed ``.usifc`` datasets and queries."""

import sqlite3
import threading

import numpy as np
import pytest

from usif.dataset import Dataset, Q
from usif.errors import DatasetError, UnsupportedVersionError, ValidationError
from usif.model import Cell, Structure

ROCKSALT = [
    [0, 0, 0],
    [0, 0.5, 0.5],
    [0.5, 0, 0.5],
    [0.5, 0.5, 0],
    [0.5, 0.5, 0.5],
    [0.5, 0, 0],
    [0, 0.5, 0],
    [0, 0, 0.5],
]


def nacl(a=5.64, energy=-10.0) -> Structure:
    return Structure.from_fractional(
        [11] * 4 + [17] * 4, ROCKSALT, Cell.cubic(a), properties={"energy": energy}
    )


def water(energy=-14.2) -> Structure:
    return Structure(
        [8, 1, 1], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]], properties={"energy": energy}
    )


def fe2o3() -> Structure:
    rng = np.random.default_rng(3)
    s = Structure([26] * 2 + [8] * 3, rng.random((5, 3)) * 4, Cell.cubic(4.0))
    s.arrays["force"] = rng.normal(size=(5, 3))
    return s


@pytest.fixture
def ds(tmp_path):
    with Dataset(tmp_path / "data.usifc") as d:
        d.add(nacl(), "nacl", "/salts", attrs={"source": "mp", "id": 1})
        d.add(
            nacl(a=5.70, energy=-9.0), "nacl-strained", "/salts/strained", attrs={"source": "dft"}
        )
        d.add(water(), "h2o", "/molecules", attrs={"source": "mp", "relaxed": True})
        d.add(fe2o3(), "fe2o3", "/oxides")
        yield d


class TestStorage:
    def test_round_trip_and_lookup(self, ds):
        assert len(ds) == 4
        assert ds["/salts/nacl"] == nacl()
        entry = ds.entry("/oxides/fe2o3")
        assert entry.path == "/oxides/fe2o3"
        assert entry.structure == fe2o3()
        assert ds.get(entry.record_hash) == fe2o3()
        assert "/salts/nacl" in ds and entry.record_hash in ds
        assert "/missing/x" not in ds and "zz" not in ds and 3 not in ds
        with pytest.raises(KeyError):
            ds["/salts/none"]

    def test_records_are_deduplicated(self, ds):
        before = ds.stats()["records"]
        e1 = ds.add(nacl(), "copy", "/other")
        assert ds.stats()["records"] == before
        assert e1.record_hash == ds.entry("/salts/nacl").record_hash
        # unnamed entries are idempotent per group
        a = ds.add(water(), group="/pool")
        b = ds.add(water(), group="/pool", attrs={"x": 1})
        assert a.id == b.id and b.attrs == {"x": 1}

    def test_named_entry_conflict_and_overwrite(self, ds):
        with pytest.raises(DatasetError, match="exists"):
            ds.add(water(), "nacl", "/salts")
        entry = ds.add(water(), "nacl", "/salts", overwrite=True)
        assert ds["/salts/nacl"] == water()
        assert entry.attrs == {"source": "mp", "id": 1}  # kept when not given

    def test_add_many_and_record_passthrough(self, tmp_path):
        with Dataset(tmp_path / "many.usifc") as d:
            structures = [nacl(a=5.0 + i / 100) for i in range(25)]
            assert (
                d.add_many(structures, "/scan", names=[f"s{i}" for i in range(25)], batch_size=10)
                == 25
            )
            assert d.count(Q.group("/scan")) == 25
            assert d["/scan/s7"] == structures[7]
            from usif.codec import encode

            entry = d.add_record(encode(water()), "w", "/raw")
            assert entry.structure == water()

    def test_link_shares_the_record(self, ds):
        records = ds.stats()["records"]
        linked = ds.link("/salts/nacl", "nacl", "/projects/demo")
        assert ds.stats()["records"] == records and len(ds) == 5
        assert linked.record_hash == ds.entry("/salts/nacl").record_hash
        assert linked.attrs == {"source": "mp", "id": 1}  # copied by default
        assert ds.link("/salts/nacl", "x", "/p", {"k": 1}).attrs == {"k": 1}
        assert ds["/projects/demo/nacl"] == nacl() and "/projects" in ds.groups()
        with pytest.raises(DatasetError, match="exists"):
            ds.link("/oxides/fe2o3", "nacl", "/projects/demo")
        assert ds.link("/oxides/fe2o3", "nacl", "/projects/demo", overwrite=True).attrs == {}
        with pytest.raises(KeyError):
            ds.link("/salts/none", "y", "/p")
        with pytest.raises(ValidationError):
            ds.link("/salts/nacl", "a/b", "/p")
        ds.remove("/salts/nacl")  # the record stays while another entry refers to it
        assert ds.stats()["unreferenced_records"] == 0
        assert ds["/p/x"] == nacl()

    def test_remove_and_compact(self, ds):
        ds.remove("/oxides/fe2o3")
        assert ds.stats()["unreferenced_records"] == 1
        ds.compact()
        stats = ds.stats()
        assert stats["unreferenced_records"] == 0 and stats["entries"] == 3
        assert "/oxides" not in ds.groups()

    def test_attrs(self, ds):
        assert ds.set_attrs("/salts/nacl", {"note": "ok"}) == {
            "source": "mp",
            "id": 1,
            "note": "ok",
        }
        assert ds.set_attrs("/salts/nacl", {"only": 1}, merge=False) == {"only": 1}
        assert ds.set_group_attrs("/salts", {"desc": "rock salt"}) == {"desc": "rock salt"}
        assert ds.group_attrs("/salts") == {"desc": "rock salt"}
        with pytest.raises(ValidationError):
            ds.set_attrs("/salts/nacl", {"bad": float("nan")})
        with pytest.raises(ValidationError):
            ds.set_attrs("/salts/nacl", {"bad": object()})

    @pytest.mark.parametrize("name", ["", "a/b", "..", "x\n", "é" * 200])
    def test_invalid_names(self, ds, name):
        with pytest.raises(ValidationError):
            ds.add(water(), name)

    @pytest.mark.parametrize("group", ["/a/../b", "/a/\x00"])
    def test_invalid_groups(self, ds, group):
        with pytest.raises(ValidationError):
            ds.add(water(), "x", group)

    def test_groups_are_created_with_parents(self, ds):
        assert {"/", "/salts", "/salts/strained", "/molecules", "/oxides"} <= set(ds.groups())

    def test_transaction_rollback(self, ds):
        with pytest.raises(RuntimeError):
            with ds.transaction():
                ds.add(water(energy=1.0), "tmp", "/scratch")
                raise RuntimeError
        assert "/scratch/tmp" not in ds
        assert ds.stats()["records"] == 4

    def test_check(self, ds):
        report = ds.check(full=True)
        assert report.ok and report.checked_records == 4

    def test_check_detects_corrupted_record(self, ds):
        conn = sqlite3.connect(ds.path)
        data = bytearray(conn.execute("SELECT data FROM records WHERE id = 1").fetchone()[0])
        data[-1] ^= 0xFF
        conn.execute("UPDATE records SET data = ? WHERE id = 1", (bytes(data),))
        conn.commit()
        conn.close()
        report = ds.check(full=True)
        assert not report.ok and "digest" in report.errors[0]

    def test_failed_transaction_keeps_the_original_error(self, ds):
        # SQLite rolls back by itself after I/O errors or a full disk; the rollback that
        # follows must not replace the error that caused it.
        with pytest.raises(ValueError, match="boom"):
            with ds.transaction():
                ds.add(nacl(), "a")
                ds._conn.execute("ROLLBACK")
                raise ValueError("boom")
        assert "/a" not in ds
        before = len(ds)
        ds.add(nacl(), "b")  # the dataset is still usable
        with pytest.raises(DatasetError, match="no transaction"):
            with ds.transaction():
                ds._conn.execute("ROLLBACK")  # work lost, then the commit fails cleanly
        assert len(ds) == before + 1


class TestModes:
    def test_read_only(self, ds, tmp_path):
        path = ds.path
        ds.close()
        with Dataset(path, "r") as ro:
            assert len(ro) == 4
            with pytest.raises(DatasetError, match="read-only"):
                ro.add(water(), "x")
        with pytest.raises(DatasetError):
            Dataset(tmp_path / "missing.usifc", "r")

    def test_closed(self, ds):
        ds.close()
        with pytest.raises(DatasetError, match="closed"):
            len(ds)

    def test_write_mode_replaces_atomically(self, ds):
        path = ds.path
        ds.close()
        with Dataset(path, "w") as new:
            new.add(water(), "only")
            with Dataset(path, "r") as old:
                assert len(old) == 4  # old file still in place
        with Dataset(path, "r") as reopened:
            assert len(reopened) == 1
        with pytest.raises(RuntimeError):
            with Dataset(path, "w") as failed:
                failed.add(nacl(), "x")
                raise RuntimeError
        with Dataset(path, "r") as reopened:
            assert len(reopened) == 1
        leftovers = {p.name for p in path.parent.iterdir()} - {path.name}
        assert all(name.startswith(path.name + "-") for name in leftovers)  # no temp files

    def test_rejects_foreign_files(self, tmp_path):
        other = tmp_path / "other.db"
        sqlite3.connect(other).execute("CREATE TABLE t(x)").connection.commit()
        with pytest.raises(DatasetError, match="not a USIF dataset"):
            Dataset(other, "r")
        junk = tmp_path / "junk.usifc"
        junk.write_bytes(b"USIF container v2 " * 100)
        with pytest.raises(DatasetError, match="Dataset.import_v2"):
            Dataset(junk, "r")

    def test_rejects_newer_schema(self, ds):
        path = ds.path
        ds.close()
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA user_version = 99")
        conn.close()
        with pytest.raises(UnsupportedVersionError):
            Dataset(path, "r")

    def test_metadata(self, ds):
        meta = ds.metadata()
        assert meta["creator"].startswith("usif ") and meta["schema_version"] == "1"

    def test_concurrent_threads(self, tmp_path):
        with Dataset(tmp_path / "t.usifc") as d:
            errors = []

            def work(i):
                try:
                    for j in range(10):
                        d.add(nacl(a=5 + i + j / 100), f"s{j}", f"/t{i}")
                except Exception as exc:  # pragma: no cover - reported below
                    errors.append(exc)

            threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert not errors and len(d) == 40


class TestQuery:
    def names(self, ds, q):
        return sorted(e.name for e in ds.query(q))

    def test_record_conditions(self, ds):
        assert self.names(ds, Q.formula("NaCl")) == ["nacl", "nacl-strained"]
        assert self.names(ds, Q.chemsys("Na-Cl")) == ["nacl", "nacl-strained"]
        assert self.names(ds, Q.chemsys(["O", "Fe"])) == ["fe2o3"]
        assert self.names(ds, Q.elements("O")) == ["fe2o3", "h2o"]
        assert self.names(ds, Q.elements("O") & ~Q.elements("H")) == ["fe2o3"]
        assert self.names(ds, Q.natoms(max=5)) == ["fe2o3", "h2o"]
        assert self.names(ds, Q.natoms(min=4, max=5)) == ["fe2o3"]
        assert self.names(ds, Q.periodic(False)) == ["h2o"]
        assert self.names(ds, Q.prop("energy") < -9.5) == ["h2o", "nacl"]
        assert self.names(ds, Q.prop("energy").between(-10, -9)) == ["nacl", "nacl-strained"]
        assert self.names(ds, ~Q.has_prop("energy")) == ["fe2o3"]
        h = ds.entry("/oxides/fe2o3").record_hash
        assert self.names(ds, Q.record(h)) == ["fe2o3"]

    def test_entry_conditions(self, ds):
        assert self.names(ds, Q.group("/salts")) == ["nacl", "nacl-strained"]
        assert self.names(ds, Q.group("/salts", recursive=False)) == ["nacl"]
        assert self.names(ds, Q.name("nacl*")) == ["nacl", "nacl-strained"]
        assert self.names(ds, Q.attr("source") == "mp") == ["h2o", "nacl"]
        assert self.names(ds, Q.attr("relaxed") == True) == ["h2o"]  # noqa: E712
        assert self.names(ds, Q.has_attr("id")) == ["nacl"]
        assert self.names(ds, Q.group("/salts") | Q.group("/oxides")) == [
            "fe2o3",
            "nacl",
            "nacl-strained",
        ]

    def test_like_wildcards_in_group_are_literal(self, ds):
        ds.add(water(), "w", "/sal_s")
        ds.add(water(energy=0.0), "w", "/sal_s_x")
        assert self.names(ds, Q.group("/sal_s")) == ["w"]

    def test_values_cannot_inject_sql(self, ds):
        evil = "x'); DROP TABLE records; --"
        assert self.names(ds, Q.formula(evil)) == []
        assert self.names(ds, Q.prop(evil) > 0) == []
        assert self.names(ds, Q.name(evil)) == []
        assert ds.stats()["records"] == 4
        with pytest.raises(ValidationError):
            Q.attr('a"b')
        with pytest.raises(ValidationError):
            Q.prop("energy") < "low"
        with pytest.raises(ValidationError):
            Q.attr("x") == [1]

    def test_limit_load_and_paging(self, tmp_path, monkeypatch):
        import usif.dataset.dataset as module

        monkeypatch.setattr(module, "PAGE_SIZE", 3)
        with Dataset(tmp_path / "p.usifc") as d:
            d.add_many(
                (nacl(a=5 + i / 10) for i in range(10)), "/g", names=[f"n{i}" for i in range(10)]
            )
            assert [e.name for e in d.query()] == [f"n{i}" for i in range(10)]
            assert len(list(d.query(limit=7))) == 7
            loaded = list(d.query(Q.name("n9"), load=True))
            assert loaded[0].structure == nacl(a=5.9)
            assert len(list(d.structures(Q.group("/g")))) == 10
            assert d.count(Q.natoms(min=100)) == 0


class TestQueryPlans:
    """Property and element conditions must be answered from their indexes."""

    @pytest.fixture
    def filled(self, tmp_path):
        with Dataset(tmp_path / "plan.usifc") as dataset:
            dataset.add_many(
                (nacl(a=5.0 + i / 100, energy=-float(i)) for i in range(60)),
                "/eos",
                names=[f"n{i}" for i in range(60)],
            )
            yield dataset

    def plan(self, dataset, where):
        sql = (
            f"SELECT COUNT(*) FROM entries e JOIN records r ON r.id = e.record_id WHERE {where.sql}"
        )
        return " ".join(
            row[3] for row in dataset._conn.execute(f"EXPLAIN QUERY PLAN {sql}", where.params)
        )

    def test_between_is_one_index_range(self, filled):
        where = Q.prop("energy").between(-20, -10)
        assert filled.count(where) == 11
        plan = self.plan(filled, where)
        assert "record_values_lookup (name=? AND value>? AND value<?)" in plan

    @pytest.mark.parametrize(
        "where",
        [Q.prop("energy") < -50, Q.has_prop("energy"), Q.elements("Na", "Cl")],
        ids=["prop", "has_prop", "elements"],
    )
    def test_conditions_use_indexes(self, filled, where):
        plan = self.plan(filled, where)
        assert "SCAN e" not in plan and "SCAN r" not in plan, plan

    def test_between_and_negation_results(self, filled):
        assert filled.count(Q.prop("energy").between(-2, 0)) == 3
        assert filled.count(~Q.prop("energy").between(-2, 0)) == 57
        assert filled.count(Q.attr("missing").between(0, 1)) == 0
        with pytest.raises(ValidationError):
            Q.prop("energy").between("a", 1)


def test_isin_matches_any_of_the_values(tmp_path):
    with Dataset(tmp_path / "d.usifc") as data:
        for i in range(4):
            data.add(nacl(5.0 + i, energy=-float(i)), f"e{i}", "/", {"tag": f"t{i}", "n": i})
        assert data.count(Q.attr("tag").isin(["t1", "t3", "zz"])) == 2
        assert data.count(Q.attr("n").isin([0, 2])) == 2
        assert data.count(Q.prop("energy").isin([-1.0, -3.0])) == 2
        assert data.count(Q.attr("tag").isin([])) == 0
        with pytest.raises(ValidationError, match="at most"):
            Q.attr("tag").isin(range(501))
        with pytest.raises(ValidationError, match="numbers"):
            Q.prop("energy").isin(["x"])


@pytest.mark.parametrize("mode", ["a", "r"])
def test_connections_use_a_large_cache_and_mmap(tmp_path, mode):
    from usif.dataset.sql import CACHE_KIB, MMAP_BYTES

    path = tmp_path / "c.usifc"
    Dataset(path).close()
    with Dataset(path, mode) as data:
        assert data._conn.execute("PRAGMA cache_size").fetchone()[0] == -CACHE_KIB
        assert data._conn.execute("PRAGMA mmap_size").fetchone()[0] in (MMAP_BYTES, 0)
