#!/usr/bin/env python
"""
Download and load the NCBI taxonomy dump into the `taxa` collection.

Downloads new_taxdump.tar.gz from the NCBI FTP site, parses rankedlineage.dmp,
names.dmp, nodes.dmp, and taxidlineage.dmp, and bulk-upserts all records into
MongoDB.

Existing records are updated for all taxonomy fields. The `clinical_notes`
field is never overwritten — it is only set on first insert.

merged.dmp and delnodes.dmp are loaded into the `taxa_retired` collection,
which is replaced wholesale on every run. Classifier databases are built on
older taxonomy snapshots, so profiles can carry IDs NCBI has since merged or
deleted; `taxa_retired` is how the app resolves them instead of treating them
as unknown.

Usage:
    python load_taxonomy.py
    python load_taxonomy.py --skip-download --dump-dir /path/to/existing/dump
    python load_taxonomy.py --dry-run

Schedule:
    Run monthly to stay current with NCBI taxonomy updates. NCBI archives
    a snapshot on the 1st of each month. The FTP path for the latest dump is:
    https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz
"""

import argparse
import array
import asyncio
import logging
import os
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz"
BATCH_SIZE = 10_000
RETIRED_COLLECTION = "taxa_retired"
RETIRED_STAGING_COLLECTION = "taxa_retired_staging"


def _build_mongo_url() -> str:
    # Env var names align with the backend's discrete-field config in
    # `backend/.env.example` so the same `.env` can drive both. `MONGODB_URI`
    # is intentionally not honored here — this script is invoked from a
    # systemd unit on the HPC that supplies discrete fields.
    username = os.getenv("MONGODB_USERNAME")
    password = os.getenv("MONGODB_PASSWORD")
    host = os.getenv("MONGODB_HOST", "localhost")
    port = os.getenv("MONGODB_PORT", "27017")
    auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")

    if bool(username) != bool(password):
        raise RuntimeError(
            "MONGODB_USERNAME and MONGODB_PASSWORD must be set together "
            "(or both unset for an unauthenticated connection)."
        )

    if username:
        return (
            f"mongodb://{username}:{password}@{host}:{port}"
            f"/?authSource={auth_source}&directConnection=true"
        )
    return f"mongodb://{host}:{port}/?directConnection=true"


def _download_dump(dest_dir: Path) -> Path:
    """Download new_taxdump.tar.gz into dest_dir and return the local path."""
    dest = dest_dir / "new_taxdump.tar.gz"
    log.info("Downloading %s → %s", TAXDUMP_URL, dest)
    urllib.request.urlretrieve(TAXDUMP_URL, dest)
    log.info("Download complete (%.1f MB)", dest.stat().st_size / 1_048_576)
    return dest


def _extract_dump(archive: Path, dest_dir: Path) -> None:
    """Extract only the files we need from the archive."""
    needed = {
        "rankedlineage.dmp",
        "names.dmp",
        "nodes.dmp",
        "taxidlineage.dmp",
        "merged.dmp",
        "delnodes.dmp",
    }
    log.info("Extracting %s from archive", needed)
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf.getmembers():
            if member.name in needed:
                tf.extract(member, path=dest_dir, filter="data")
    log.info("Extraction complete")


def _parse_names(names_path: Path) -> dict[int, str]:
    """
    Parse names.dmp and return a mapping of taxon_id → scientific name.

    names.dmp contains multiple name types per taxon (scientific name,
    synonym, blast name, etc.). We keep only the scientific name.
    """
    log.info("Parsing names.dmp…")
    names: dict[int, str] = {}
    with open(names_path, encoding="utf-8") as fh:
        for line in fh:
            parts = [p.strip() for p in line.split("\t|\t")]
            if len(parts) < 4:
                continue
            name_class = parts[3].rstrip("\t|").strip()
            if name_class == "scientific name":
                names[int(parts[0])] = parts[1]
    log.info("Parsed %d scientific names", len(names))
    return names


def _or_none(s: str) -> str | None:
    return s if s else None


def _parse_rankedlineage(lineage_path: Path) -> dict[int, dict]:
    """
    Parse rankedlineage.dmp.

    Format (tab-pipe-tab delimited):
        tax_id | name | species | genus | family | order | class |
        phylum | kingdom | superkingdom |

    Returns a dict of taxon_id → lineage fields (excluding name, which
    comes from names.dmp for consistency).
    """
    log.info("Parsing rankedlineage.dmp…")
    lineages: dict[int, dict] = {}
    with open(lineage_path, encoding="utf-8") as fh:
        for line in fh:
            parts = [p.strip() for p in line.split("\t|\t")]
            # Strip trailing \t| on last field
            parts[-1] = parts[-1].rstrip("\t|").strip()

            if len(parts) < 10:
                continue

            lineages[int(parts[0])] = {
                "species": _or_none(parts[2]),
                "genus": _or_none(parts[3]),
                "family": _or_none(parts[4]),
                "order": _or_none(parts[5]),
                "class_": _or_none(parts[6]),  # "class" is a Python keyword
                "phylum": _or_none(parts[7]),
                "kingdom": _or_none(parts[8]),
                "superkingdom": _or_none(parts[9]),
            }

    log.info("Parsed %d lineage records", len(lineages))
    return lineages


def _parse_nodes(nodes_path: Path) -> dict[int, str | None]:
    """
    Parse nodes.dmp and return a mapping of taxon_id → rank.

    nodes.dmp is the authoritative source for rank. Format is tab-pipe-tab
    delimited; tax_id is field 0, rank is field 2. 'no rank' is stored as
    None to be consistent with what the taxpasta reader produces.
    """
    log.info("Parsing nodes.dmp…")
    ranks: dict[int, str | None] = {}
    with open(nodes_path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.split("\t|\t")
            if len(parts) < 3:
                continue
            rank = parts[2].strip()
            ranks[int(parts[0].strip())] = rank if rank and rank != "no rank" else None
    log.info("Parsed %d rank records", len(ranks))
    return ranks


def _parse_taxidlineage(lineage_path: Path) -> dict[int, array.array[int]]:
    """
    Parse taxidlineage.dmp and return a mapping of taxon_id → ancestor IDs.

    Format: ``tax_id | space-separated ancestor IDs, outermost first |``.
    Neither the taxon itself nor root (1) is part of a lineage, so top-level
    taxa such as root, "cellular organisms" (131567) and Viruses (10239) have
    an empty one.

    Ancestors are held as ``array('I')`` (4 bytes per ID) rather than lists of
    ints (a pointer plus a ~28-byte int object per ID): the dump has ~3M
    lineages, and parsing this file alone peaks at ~1 GB RSS as it is. NCBI
    taxon IDs are far below the 2**32 limit.
    """
    log.info("Parsing taxidlineage.dmp…")
    ancestors: dict[int, array.array[int]] = {}
    with open(lineage_path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t|\t")
            if len(parts) < 2:
                continue
            ids = parts[1].rstrip("\t|").split()
            ancestors[int(parts[0].strip())] = array.array("I", map(int, ids))
    log.info("Parsed %d taxid lineages", len(ancestors))
    return ancestors


def _parse_merged(merged_path: Path) -> dict[int, int]:
    """
    Parse merged.dmp and return a mapping of old taxon_id → current taxon_id.

    Format: ``old_tax_id | new_tax_id |``.
    """
    log.info("Parsing merged.dmp…")
    merged: dict[int, int] = {}
    with open(merged_path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t|\t")
            if len(parts) < 2:
                continue
            merged[int(parts[0].strip())] = int(parts[1].rstrip("\t|").strip())
    log.info("Parsed %d merged taxon IDs", len(merged))
    return merged


def _parse_delnodes(delnodes_path: Path) -> set[int]:
    """
    Parse delnodes.dmp and return the set of deleted taxon IDs.

    Format: ``tax_id |``.
    """
    log.info("Parsing delnodes.dmp…")
    deleted: set[int] = set()
    with open(delnodes_path, encoding="utf-8") as fh:
        for line in fh:
            taxon_id = line.split("\t|")[0].strip()
            if taxon_id:
                deleted.add(int(taxon_id))
    log.info("Parsed %d deleted taxon IDs", len(deleted))
    return deleted


def _retired_documents(
    merged: dict[int, int], deleted: set[int], current_ids: set[int]
) -> list[dict]:
    """
    Build `taxa_retired` documents from the parsed merged and deleted IDs.

    An ID that is both merged and deleted, or retired while still present in
    the current taxonomy, means the dump is inconsistent. Loading it would give
    the app two answers for one ID, so this raises instead.

    A merge target missing from the current taxonomy is logged but kept: the
    app reports such IDs as unplaced rather than dropping their reads.
    """
    both = merged.keys() & deleted
    if both:
        raise ValueError(
            f"{len(both)} taxon IDs are both merged and deleted, e.g. "
            f"{sorted(both)[:5]}"
        )
    still_current = (merged.keys() | deleted) & current_ids
    if still_current:
        raise ValueError(
            f"{len(still_current)} retired taxon IDs are still in the current "
            f"taxonomy, e.g. {sorted(still_current)[:5]}"
        )

    dangling = {new for new in merged.values() if new not in current_ids}
    if dangling:
        log.warning(
            "%d merge targets are not in the current taxonomy, e.g. %s",
            len(dangling),
            sorted(dangling)[:5],
        )

    docs: list[dict] = [
        {"taxon_id": old, "status": "merged", "merged_into": new}
        for old, new in merged.items()
    ]
    docs.extend(
        {"taxon_id": taxon_id, "status": "deleted", "merged_into": None}
        for taxon_id in deleted
    )
    return docs


async def _replace_retired(db: AsyncIOMotorDatabase, docs: list[dict]) -> None:
    """
    Replace the `taxa_retired` collection with *docs*.

    Written to a staging collection and swapped in with a rename, so the app
    never reads a half-written or empty collection while this runs — during
    that window merged IDs would otherwise show up as unknown.
    """
    staging = db[RETIRED_STAGING_COLLECTION]
    await staging.drop()
    await staging.create_index("taxon_id", unique=True)
    for batch_start in range(0, len(docs), BATCH_SIZE):
        await staging.insert_many(
            docs[batch_start : batch_start + BATCH_SIZE], ordered=False
        )
    await staging.rename(RETIRED_COLLECTION, dropTarget=True)
    log.info("Replaced %s with %d documents", RETIRED_COLLECTION, len(docs))


async def load_taxonomy(dump_dir: Path, dry_run: bool) -> None:
    names = _parse_names(dump_dir / "names.dmp")
    lineages = _parse_rankedlineage(dump_dir / "rankedlineage.dmp")
    ranks = _parse_nodes(dump_dir / "nodes.dmp")

    taxon_ids = set(names.keys()) | set(lineages.keys())
    log.info("Total unique taxon IDs to upsert: %d", len(taxon_ids))

    ancestors = _parse_taxidlineage(dump_dir / "taxidlineage.dmp")
    # Built before the dry-run exit so a dry run also validates consistency.
    retired_docs = _retired_documents(
        _parse_merged(dump_dir / "merged.dmp"),
        _parse_delnodes(dump_dir / "delnodes.dmp"),
        taxon_ids,
    )

    if dry_run:
        log.info("Dry run — no writes performed.")
        return

    db_name = os.getenv("MONGODB_DB_NAME", "meta-vis-dev")
    client: AsyncIOMotorClient = AsyncIOMotorClient(_build_mongo_url())
    db = client[db_name]

    # Ensure index exists
    await db["taxa"].create_index("taxon_id", unique=True)

    now = datetime.now(timezone.utc)
    dump_version = now.strftime("%Y-%m-%d")

    taxon_id_list = list(taxon_ids)
    total = len(taxon_id_list)
    upserted = 0
    modified = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = taxon_id_list[batch_start : batch_start + BATCH_SIZE]
        ops = []

        for taxon_id in batch:
            name = names.get(taxon_id, str(taxon_id))
            lin = lineages.get(taxon_id, {})
            rank = ranks.get(taxon_id)
            # None (not []) when the dump has no lineage for this taxon, so the
            # app can tell "unplaceable" apart from a top-level taxon's
            # genuinely empty one.
            lineage_ids = ancestors.get(taxon_id)
            ancestor_ids = list(lineage_ids) if lineage_ids is not None else None

            ncbi_url = (
                f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi"
                f"?id={taxon_id}"
            )

            ops.append(
                UpdateOne(
                    {"taxon_id": taxon_id},
                    {
                        # Always update taxonomy fields
                        "$set": {
                            "name": name,
                            "rank": rank,
                            "superkingdom": lin.get("superkingdom"),
                            "kingdom": lin.get("kingdom"),
                            "phylum": lin.get("phylum"),
                            "class": lin.get("class_"),
                            "order": lin.get("order"),
                            "family": lin.get("family"),
                            "genus": lin.get("genus"),
                            "species": lin.get("species"),
                            "ancestor_ids": ancestor_ids,
                            "ncbi_url": ncbi_url,
                            "taxdump_version": dump_version,
                            "updated_at": now,
                        },
                        # Only set on first insert — never overwrite clinician notes
                        "$setOnInsert": {
                            "taxon_id": taxon_id,
                            "clinical_notes": None,
                        },
                    },
                    upsert=True,
                )
            )

        result = await db["taxa"].bulk_write(ops, ordered=False)
        upserted += result.upserted_count
        modified += result.modified_count

        pct = min(100, (batch_start + len(batch)) / total * 100)
        log.info(
            "Progress: %.0f%% (%d/%d) — upserted: %d  modified: %d",
            pct,
            batch_start + len(batch),
            total,
            upserted,
            modified,
        )

    log.info(
        "Done. Total upserted (new): %d  Total modified (updated): %d",
        upserted,
        modified,
    )

    await _replace_retired(db, retired_docs)

    # Upserts never delete, so taxa that NCBI merged or deleted since an earlier
    # load keep their old document. taxa_retired takes precedence in the app;
    # this only makes the leftovers visible.
    stale = await db["taxa"].count_documents({"updated_at": {"$lt": now}})
    if stale:
        log.warning(
            "%d taxa documents were not in this dump and are stale; "
            "taxa_retired takes precedence for these IDs",
            stale,
        )
    client.close()


async def main(skip_download: bool, dump_dir_arg: str | None, dry_run: bool) -> None:
    if dump_dir_arg:
        dump_dir = Path(dump_dir_arg)
        log.info("Using existing dump directory: %s", dump_dir)
    else:
        tmp = tempfile.mkdtemp(prefix="ncbi_taxdump_")
        dump_dir = Path(tmp)
        log.info("Working in temp directory: %s", dump_dir)

        if not skip_download:
            archive = _download_dump(dump_dir)
            _extract_dump(archive, dump_dir)
            archive.unlink()  # free space after extraction

    await load_taxonomy(dump_dir, dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download; use --dump-dir to point at existing extracted files",
    )
    parser.add_argument(
        "--dump-dir",
        default=None,
        help="Path to directory containing already-extracted .dmp files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files but do not write to MongoDB",
    )
    args = parser.parse_args()
    asyncio.run(main(args.skip_download, args.dump_dir, args.dry_run))
