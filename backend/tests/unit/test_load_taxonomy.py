# tests/unit/test_load_taxonomy.py

import importlib.util
import logging
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def loader() -> ModuleType:
    """Load backend/load_taxonomy.py as a module without executing main()."""
    # backend/tests/unit/test_load_taxonomy.py -> backend is parents[2]
    path = Path(__file__).resolve().parents[2] / "load_taxonomy.py"
    spec = importlib.util.spec_from_file_location("load_taxonomy_script", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["load_taxonomy_script"] = module
    spec.loader.exec_module(module)
    return module


def write_dmp(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content)
    return p


# Copied from a real NCBI dump: tab-pipe-tab separators, a trailing tab-pipe,
# a trailing space after the last ancestor ID, and root (1) left out of every
# lineage.
TAXIDLINEAGE_DMP = (
    "1\t|\t\t|\n"
    "131567\t|\t\t|\n"
    "561\t|\t131567 2 3379134 1224 1236 91347 543 \t|\n"
    "562\t|\t131567 2 3379134 1224 1236 91347 543 561 \t|\n"
)

MERGED_DMP = "12\t|\t74109\t|\n30\t|\t29\t|\n"

DELNODES_DMP = "3418497\t|\n3418496\t|\n"


# ---------------------------------------------------------------------------
# _parse_taxidlineage
# ---------------------------------------------------------------------------


def test_parse_taxidlineage_keeps_outermost_first_order(loader, tmp_path):
    path = write_dmp(tmp_path, "taxidlineage.dmp", TAXIDLINEAGE_DMP)

    ancestors = loader._parse_taxidlineage(path)

    assert list(ancestors[562]) == [131567, 2, 3379134, 1224, 1236, 91347, 543, 561]


def test_parse_taxidlineage_excludes_the_taxon_itself(loader, tmp_path):
    path = write_dmp(tmp_path, "taxidlineage.dmp", TAXIDLINEAGE_DMP)

    ancestors = loader._parse_taxidlineage(path)

    assert 561 not in ancestors[561]


def test_parse_taxidlineage_top_level_taxa_have_empty_lineage(loader, tmp_path):
    path = write_dmp(tmp_path, "taxidlineage.dmp", TAXIDLINEAGE_DMP)

    ancestors = loader._parse_taxidlineage(path)

    # Present but empty — distinct from a taxon missing from the dump.
    assert list(ancestors[1]) == []
    assert list(ancestors[131567]) == []


def test_parse_taxidlineage_omits_root_from_lineages(loader, tmp_path):
    path = write_dmp(tmp_path, "taxidlineage.dmp", TAXIDLINEAGE_DMP)

    ancestors = loader._parse_taxidlineage(path)

    assert 1 not in ancestors[562]


def test_parse_taxidlineage_skips_malformed_lines(loader, tmp_path):
    path = write_dmp(tmp_path, "taxidlineage.dmp", "\n" + TAXIDLINEAGE_DMP)

    ancestors = loader._parse_taxidlineage(path)

    assert set(ancestors) == {1, 131567, 561, 562}


# ---------------------------------------------------------------------------
# _parse_merged / _parse_delnodes
# ---------------------------------------------------------------------------


def test_parse_merged_maps_old_to_new(loader, tmp_path):
    path = write_dmp(tmp_path, "merged.dmp", MERGED_DMP)

    assert loader._parse_merged(path) == {12: 74109, 30: 29}


def test_parse_delnodes_returns_ids(loader, tmp_path):
    path = write_dmp(tmp_path, "delnodes.dmp", DELNODES_DMP)

    assert loader._parse_delnodes(path) == {3418497, 3418496}


# ---------------------------------------------------------------------------
# _retired_documents
# ---------------------------------------------------------------------------


def test_retired_documents_builds_merged_and_deleted(loader):
    docs = loader._retired_documents({12: 74109}, {3418497}, {74109})

    assert sorted(docs, key=lambda d: d["taxon_id"]) == [
        {"taxon_id": 12, "status": "merged", "merged_into": 74109},
        {"taxon_id": 3418497, "status": "deleted", "merged_into": None},
    ]


def test_retired_documents_rejects_id_both_merged_and_deleted(loader):
    with pytest.raises(ValueError, match="both merged and deleted"):
        loader._retired_documents({12: 74109}, {12}, {74109})


def test_retired_documents_rejects_retired_id_still_current(loader):
    with pytest.raises(ValueError, match="still in the current taxonomy"):
        loader._retired_documents({12: 74109}, set(), {12, 74109})


def test_retired_documents_warns_on_dangling_merge_target(loader, caplog):
    with caplog.at_level(logging.WARNING):
        docs = loader._retired_documents({12: 74109}, set(), set())

    # Kept, so the app can report the ID as unplaced instead of losing it.
    assert docs == [{"taxon_id": 12, "status": "merged", "merged_into": 74109}]
    assert "not in the current taxonomy" in caplog.text


# ---------------------------------------------------------------------------
# _replace_retired
# ---------------------------------------------------------------------------


async def test_replace_retired_replaces_previous_contents(loader, fake_db):
    await fake_db["taxa_retired"].insert_one(
        {"taxon_id": 999, "status": "deleted", "merged_into": None}
    )
    doc = {"taxon_id": 12, "status": "merged", "merged_into": 74109}

    # insert_many adds `_id` to the dicts it is given, so pass a copy.
    await loader._replace_retired(fake_db, [dict(doc)])

    stored = await fake_db["taxa_retired"].find({}, {"_id": 0}).to_list(None)
    assert stored == [doc]


async def test_replace_retired_leaves_no_staging_collection(loader, fake_db):
    await loader._replace_retired(
        fake_db, [{"taxon_id": 12, "status": "merged", "merged_into": 74109}]
    )

    assert "taxa_retired_staging" not in await fake_db.list_collection_names()


# ---------------------------------------------------------------------------
# _extract_dump
# ---------------------------------------------------------------------------


def test_extract_dump_includes_lineage_and_retired_files(loader, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    wanted = [
        "names.dmp",
        "nodes.dmp",
        "rankedlineage.dmp",
        "taxidlineage.dmp",
        "merged.dmp",
        "delnodes.dmp",
    ]
    for name in [*wanted, "citations.dmp"]:
        (src / name).write_text("")
    archive = tmp_path / "new_taxdump.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for f in src.iterdir():
            tf.add(f, arcname=f.name)
    dest = tmp_path / "dest"
    dest.mkdir()

    loader._extract_dump(archive, dest)

    assert sorted(p.name for p in dest.iterdir()) == sorted(wanted)
