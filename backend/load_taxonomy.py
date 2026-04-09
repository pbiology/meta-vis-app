#!/usr/bin/env python
"""
Download and load the NCBI taxonomy dump into the `taxa` collection.

Downloads new_taxdump.tar.gz from the NCBI FTP site, parses rankedlineage.dmp
and names.dmp, and bulk-upserts all records into MongoDB.

Existing records are updated for all taxonomy fields. The `clinical_notes`
field is never overwritten — it is only set on first insert.

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
import asyncio
import logging
import os
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TAXDUMP_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz"
)
BATCH_SIZE = 10_000


def _build_mongo_url() -> str:
    username = os.getenv("MONGO_INITDB_ROOT_USERNAME", "admin")
    password = os.getenv("MONGO_ROOT_PASSWORD")
    host = os.getenv("MONGODB_HOST", "localhost")
    port = os.getenv("MONGODB_PORT", "27017")
    if password:
        return f"mongodb://{username}:{password}@{host}:{port}/?authSource=admin"
    return f"mongodb://{host}:{port}"


def _download_dump(dest_dir: Path) -> Path:
    """Download new_taxdump.tar.gz into dest_dir and return the local path."""
    dest = dest_dir / "new_taxdump.tar.gz"
    log.info("Downloading %s → %s", TAXDUMP_URL, dest)
    urllib.request.urlretrieve(TAXDUMP_URL, dest)
    log.info("Download complete (%.1f MB)", dest.stat().st_size / 1_048_576)
    return dest


def _extract_dump(archive: Path, dest_dir: Path) -> None:
    """Extract only the files we need from the archive."""
    needed = {"rankedlineage.dmp", "names.dmp"}
    log.info("Extracting %s from archive", needed)
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf.getmembers():
            if member.name in needed:
                tf.extract(member, path=dest_dir)
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


def _or_none(s: str):
    return s if s else None


def _parse_rankedlineage(
    lineage_path: Path,
) -> dict[int, dict]:
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
                "class_": _or_none(parts[6]),   # "class" is a Python keyword
                "phylum": _or_none(parts[7]),
                "kingdom": _or_none(parts[8]),
                "superkingdom": _or_none(parts[9]),
            }

    log.info("Parsed %d lineage records", len(lineages))
    return lineages


def _derive_rank(taxon_id: int, lineage: dict, name: str) -> str | None:
    """
    Derive a taxon's own rank from the lineage fields.

    rankedlineage.dmp gives us the lineage but not the taxon's own rank
    directly. We approximate by checking which lineage level the taxon's
    name matches. This covers the common cases; for unusual ranks
    (no rank, clade, etc.) it returns None.
    """
    checks = [
        ("species", lineage.get("species")),
        ("genus", lineage.get("genus")),
        ("family", lineage.get("family")),
        ("order", lineage.get("order")),
        ("class", lineage.get("class_")),
        ("phylum", lineage.get("phylum")),
        ("kingdom", lineage.get("kingdom")),
        ("superkingdom", lineage.get("superkingdom")),
    ]
    for rank, value in checks:
        if value and value == name:
            return rank
    return None


async def load_taxonomy(dump_dir: Path, dry_run: bool) -> None:
    names = _parse_names(dump_dir / "names.dmp")
    lineages = _parse_rankedlineage(dump_dir / "rankedlineage.dmp")

    taxon_ids = set(names.keys()) | set(lineages.keys())
    log.info("Total unique taxon IDs to upsert: %d", len(taxon_ids))

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
            rank = _derive_rank(taxon_id, lin, name)

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
            pct, batch_start + len(batch), total, upserted, modified,
        )

    log.info(
        "Done. Total upserted (new): %d  Total modified (updated): %d",
        upserted,
        modified,
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