#!/usr/bin/env python
"""
Ingest pipeline results into meta-vis-app.

The CLI packages every referenced file into a single tar.gz bundle and uploads
it via multipart to the backend. This works against any reachable backend
(local, remote, in-cluster) — the server materialises the bundle into a
temporary directory and runs the existing orchestrator against those paths.

Subcommands:

  taxprofiler  Ingest a taxprofiler (shotgun metagenomics) case
  trana        Ingest a Trana (16S amplicon, ONT, Emu) case

Examples:

    python ingest.py taxprofiler \\
        --case-id slowtiger \\
        --multiqc  /path/to/multiqc_data.json \\
        --pipeline-info /path/to/software_versions.yml \\
        --classifier "kraken2 db=k2_pluspf taxpasta=/path/kraken2.tsv krona=/path/kraken2.html" \\
        --sample "sample_id=PE-04-28 type=sample material=DNA column_kraken2=PE-04-28_k2_pluspf" \\
        --password yourpassword

    python ingest.py trana \\
        --case-id trana_run1 \\
        --pipeline-info /path/to/software_versions.yml \\
        --sample "sample_id=S1 type=sample material=DNA abundance_path=/path/to/S1_rel-abundance.tsv" \\
        --password yourpassword

Backward-compatible: calling without a subcommand (old style) routes to taxprofiler.

The bundle layout the CLI produces must match what the server's loader expects.
The canonical layout is documented in backend/app/ingestor/loader.py; the
constants below mirror it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Bundle layout — keep in sync with backend/app/ingestor/loader.py
# ---------------------------------------------------------------------------

MANIFEST_ARC = "manifest.json"
MULTIQC_ARC = "multiqc/multiqc_data.json"
MULTIQC_REPORT_DIR = "multiqc_report"
PIPELINE_INFO_DIR = "pipeline_info"
METAVAL_DIR = "metaval"


def _classifier_taxpasta_arcname(name: str, src: Path) -> str:
    return f"classifiers/{name}/taxpasta/{src.name}"


def _classifier_krona_arcname(name: str, src: Path) -> str:
    return f"classifiers/{name}/krona/{src.name}"


def _sample_abundance_arcname(sample_id: str) -> str:
    return f"samples/{sample_id}/abundance.tsv"


def _sample_krona_arcname(sample_id: str) -> str:
    return f"samples/{sample_id}/krona.html"


def _sample_nanoplot_arcname(sample_id: str, kind: str) -> str:
    return f"samples/{sample_id}/nanoplot_{kind}/NanoStats.txt"


# ---------------------------------------------------------------------------
# Auth + timing helpers
# ---------------------------------------------------------------------------


def _ms() -> int:
    return int(time.time() * 1000)


_INGEST_ROLES = {"writer", "admin"}


def _check_unique_classifier_names(classifier_names: list[str]) -> None:
    seen: set[str] = set()
    dups: list[str] = []
    for name in classifier_names:
        if name in seen:
            dups.append(name)
        seen.add(name)
    if dups:
        print(f"Duplicate --classifier name(s): {sorted(set(dups))}.")
        sys.exit(1)


def _check_unique_sample_ids(samples: list[dict]) -> None:
    seen: set[str] = set()
    dups: list[str] = []
    for s in samples:
        sid = s["sample_id"]
        if sid in seen:
            dups.append(sid)
        seen.add(sid)
    if dups:
        print(f"Duplicate sample_id(s) within this case: {sorted(set(dups))}.")
        sys.exit(1)


def get_session(
    base_url: str, username: str, password: str
) -> tuple[requests.Session, int]:
    """Return (session, login_ms). Exits if the user's role can't ingest."""
    t0 = _ms()
    session = requests.Session()
    resp = session.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    login_ms = _ms() - t0
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}")
        sys.exit(1)
    data = resp.json()
    print(f"Logged in as {data['username']} ({data['role']})")
    if data["role"] not in _INGEST_ROLES:
        print(
            f"User '{data['username']}' has role '{data['role']}' which cannot "
            f"ingest cases. Required role: one of {sorted(_INGEST_ROLES)}."
        )
        sys.exit(1)
    csrf_token = session.cookies.get("csrf_token")
    if csrf_token:
        session.headers["X-CSRF-Token"] = csrf_token
    return session, login_ms


def check_case_available(session: requests.Session, base_url: str, case_id: str) -> None:
    """Fail fast if `case_id` is already taken. The server rejects duplicates,
    but it does so only after the bundle is uploaded and extracted — wasting
    minutes of wall time for a result that's knowable in one round-trip."""
    resp = session.get(f"{base_url}/api/v1/cases/{case_id}")
    if resp.status_code == 200:
        print(
            f"Case '{case_id}' already exists on the server. "
            "Choose a different --case-id or delete the existing case first."
        )
        sys.exit(1)
    # 404 is the happy path (case is free). Any other status: warn and continue
    # — the real ingest will surface the underlying error.
    if resp.status_code not in (200, 404):
        print(
            f"Warning: preflight case check returned {resp.status_code}: "
            f"{resp.text[:200]}. Continuing anyway."
        )


# ---------------------------------------------------------------------------
# Bundle building
# ---------------------------------------------------------------------------


def _check_file(path: str, label: str) -> Path:
    p = Path(path)
    if not p.is_file():
        print(f"{label} is not a file: {path}")
        sys.exit(1)
    return p


def _check_dir(path: str, label: str) -> Path:
    p = Path(path)
    if not p.is_dir():
        print(f"{label} is not a directory: {path}")
        sys.exit(1)
    return p


def _add_file(
    tar: tarfile.TarFile, src: Path, arcname: str, seen: dict[Path, str]
) -> None:
    """Add a file by absolute-source-path-dedup so duplicates collapse to one entry."""
    src_resolved = src.resolve()
    if src_resolved in seen:
        # already added; skip (callers handle keying via the arcname they chose)
        return
    seen[src_resolved] = arcname
    # Dereference symlinks so the server (which rejects symlink members) gets
    # plain regular files.
    tar.add(src_resolved, arcname=arcname, recursive=False)


def _add_tree(tar: tarfile.TarFile, src_root: Path, arc_prefix: str) -> None:
    """Add every regular file under src_root, preserving relative subpaths under
    arc_prefix. Symlinks are dereferenced."""
    src_root = src_root.resolve()
    for dirpath, _dirnames, filenames in os.walk(src_root, followlinks=True):
        for fn in filenames:
            f = Path(dirpath) / fn
            rel = f.resolve().relative_to(src_root)
            arc = f"{arc_prefix}/{rel.as_posix()}"
            tar.add(f.resolve(), arcname=arc, recursive=False)


def build_taxprofiler_bundle(
    out_path: Path,
    *,
    case_id: str,
    ticket_id: str | None,
    order_date: str | None,
    multiqc_path: str,
    multiqc_report_path: str | None,
    pipeline_info_path: str,
    metaval_dir: str | None,
    classifiers: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    analysis_type: str | None,
    sequencing_platform: str | None,
) -> None:
    """Write a taxprofiler ingest bundle to out_path. Raises SystemExit on
    invalid inputs (missing files etc.)."""

    multiqc_src = _check_file(multiqc_path, "MultiQC JSON")
    pipeline_info_src = _check_file(pipeline_info_path, "pipeline-info YAML")
    multiqc_report_src = (
        _check_file(multiqc_report_path, "MultiQC HTML report")
        if multiqc_report_path
        else None
    )
    metaval_src = _check_dir(metaval_dir, "metaval directory") if metaval_dir else None

    classifier_taxpasta_src: dict[str, Path] = {}
    classifier_krona_src: dict[str, Path] = {}
    classifiers_with_krona: list[str] = []
    for clf in classifiers:
        classifier_taxpasta_src[clf["name"]] = _check_file(
            clf["taxpasta"], f"taxpasta TSV for {clf['name']}"
        )
        if clf.get("krona"):
            classifier_krona_src[clf["name"]] = _check_file(
                clf["krona"], f"krona HTML for {clf['name']}"
            )
            classifiers_with_krona.append(clf["name"])

    manifest = {
        "case_id": case_id,
        "ticket_id": ticket_id,
        "order_date": order_date,
        "classifiers": [{"name": c["name"], "db": c["db"]} for c in classifiers],
        "samples": samples,
        "has_metaval": metaval_src is not None,
        "classifiers_with_krona": classifiers_with_krona,
        "has_multiqc_report": multiqc_report_src is not None,
        "analysis_type": analysis_type,
        "sequencing_platform": sequencing_platform,
    }

    seen: dict[Path, str] = {}
    # gzip level 1: metaval HTML / BLAST text compresses ~4x, but level-9
    # costs ~10x the CPU for ~no extra win. Level-1 hits the sweet spot —
    # smaller wire payload (fits the 2 GiB cap), fast on the client, fast
    # to decompress on the server. The server auto-detects compression.
    with tarfile.open(out_path, mode="w:gz", compresslevel=1) as tar:
        _add_file(tar, multiqc_src, MULTIQC_ARC, seen)
        _add_file(
            tar,
            pipeline_info_src,
            f"{PIPELINE_INFO_DIR}/{pipeline_info_src.name}",
            seen,
        )
        if multiqc_report_src is not None:
            _add_file(
                tar,
                multiqc_report_src,
                f"{MULTIQC_REPORT_DIR}/{multiqc_report_src.name}",
                seen,
            )
        for name, src in classifier_taxpasta_src.items():
            _add_file(tar, src, _classifier_taxpasta_arcname(name, src), seen)
        for name, src in classifier_krona_src.items():
            _add_file(tar, src, _classifier_krona_arcname(name, src), seen)
        if metaval_src is not None:
            _add_tree(tar, metaval_src, METAVAL_DIR)

        _add_manifest(tar, manifest)


def build_trana_bundle(
    out_path: Path,
    *,
    case_id: str,
    ticket_id: str | None,
    order_date: str | None,
    multiqc_report_path: str | None,
    pipeline_info_path: str,
    samples: list[dict[str, Any]],
    analysis_type: str | None,
    sequencing_platform: str | None,
) -> None:
    pipeline_info_src = _check_file(pipeline_info_path, "pipeline-info YAML")
    multiqc_report_src = (
        _check_file(multiqc_report_path, "MultiQC HTML report")
        if multiqc_report_path
        else None
    )

    # Validate every per-sample path up-front so we fail before touching the tar.
    resolved_samples: list[dict[str, Any]] = []
    for s in samples:
        abundance = _check_file(
            s["abundance_path"], f"abundance TSV for {s['sample_id']}"
        )
        krona = (
            _check_file(s["krona_path"], f"krona HTML for {s['sample_id']}")
            if s.get("krona_path")
            else None
        )
        np_unproc = (
            _check_file(
                s["nanoplot_unprocessed_path"],
                f"NanoStats unprocessed for {s['sample_id']}",
            )
            if s.get("nanoplot_unprocessed_path")
            else None
        )
        np_proc = (
            _check_file(
                s["nanoplot_processed_path"],
                f"NanoStats processed for {s['sample_id']}",
            )
            if s.get("nanoplot_processed_path")
            else None
        )
        resolved_samples.append(
            {
                "meta": {
                    "subject_id": s.get("subject_id"),
                    "sample_id": s["sample_id"],
                    "sample_type": s["sample_type"],
                    "material": s["material"],
                    "sample_source": s.get("sample_source", "N/A"),
                    "has_krona": krona is not None,
                    "has_nanoplot_unprocessed": np_unproc is not None,
                    "has_nanoplot_processed": np_proc is not None,
                },
                "abundance": abundance,
                "krona": krona,
                "nanoplot_unprocessed": np_unproc,
                "nanoplot_processed": np_proc,
            }
        )

    manifest = {
        "case_id": case_id,
        "ticket_id": ticket_id,
        "order_date": order_date,
        "samples": [rs["meta"] for rs in resolved_samples],
        "has_multiqc_report": multiqc_report_src is not None,
        "analysis_type": analysis_type,
        "sequencing_platform": sequencing_platform,
    }

    seen: dict[Path, str] = {}
    with tarfile.open(out_path, mode="w:gz", compresslevel=1) as tar:
        _add_file(
            tar,
            pipeline_info_src,
            f"{PIPELINE_INFO_DIR}/{pipeline_info_src.name}",
            seen,
        )
        if multiqc_report_src is not None:
            _add_file(
                tar,
                multiqc_report_src,
                f"{MULTIQC_REPORT_DIR}/{multiqc_report_src.name}",
                seen,
            )
        for rs in resolved_samples:
            sid = rs["meta"]["sample_id"]
            _add_file(tar, rs["abundance"], _sample_abundance_arcname(sid), seen)
            if rs["krona"]:
                _add_file(tar, rs["krona"], _sample_krona_arcname(sid), seen)
            if rs["nanoplot_unprocessed"]:
                _add_file(
                    tar,
                    rs["nanoplot_unprocessed"],
                    _sample_nanoplot_arcname(sid, "unprocessed"),
                    seen,
                )
            if rs["nanoplot_processed"]:
                _add_file(
                    tar,
                    rs["nanoplot_processed"],
                    _sample_nanoplot_arcname(sid, "processed"),
                    seen,
                )

        _add_manifest(tar, manifest)


def _add_manifest(tar: tarfile.TarFile, manifest: dict[str, Any]) -> None:
    import io

    data = json.dumps(manifest, indent=2).encode("utf-8")
    info = tarfile.TarInfo(name=MANIFEST_ARC)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


# ---------------------------------------------------------------------------
# Taxprofiler subcommand
# ---------------------------------------------------------------------------


def parse_classifier(raw: str) -> dict:
    tokens = raw.split()
    if not tokens:
        print("Empty --classifier argument")
        sys.exit(1)
    name = tokens[0]
    parts = {}
    for token in tokens[1:]:
        if "=" not in token:
            print(f"Invalid classifier token '{token}' — expected key=value")
            sys.exit(1)
        k, v = token.split("=", 1)
        parts[k.strip()] = v.strip()
    required = {"db", "taxpasta"}
    missing = required - parts.keys()
    if missing:
        print(f"Classifier '{name}' is missing required keys: {missing}")
        sys.exit(1)
    return {
        "name": name,
        "db": parts["db"],
        "taxpasta": parts["taxpasta"],
        "krona": parts.get("krona"),
    }


def parse_sample(raw: str, classifier_names: list) -> dict:
    parts = {}
    for token in raw.split():
        if "=" not in token:
            print(f"Invalid sample token '{token}' — expected key=value")
            sys.exit(1)
        k, v = token.split("=", 1)
        parts[k.strip()] = v.strip()

    required = {"sample_id", "type", "material"}
    missing = required - parts.keys()
    if missing:
        print(f"Sample is missing required keys: {missing}")
        sys.exit(1)

    sample_id = parts["sample_id"]
    classifier_set = set(classifier_names)
    columns = {}
    unknown_column_keys = []
    for key, value in parts.items():
        if not key.startswith("column_"):
            continue
        clf_name = key[len("column_") :]
        if clf_name in classifier_set:
            columns[clf_name] = value
        else:
            unknown_column_keys.append(key)

    # Unknown column_X=... was silently dropped by previous CLI versions, which
    # produced empty profiles in the DB without warning. Now an explicit error.
    if unknown_column_keys:
        print(
            f"Sample '{sample_id}' references classifier(s) that were not declared "
            f"via --classifier: {unknown_column_keys}. "
            f"Declared classifiers: {sorted(classifier_set)}."
        )
        sys.exit(1)

    if not columns:
        print(
            f"Sample '{sample_id}' has no classifier columns "
            f"(expected one column_<name>=... per --classifier)."
        )
        sys.exit(1)

    return {
        "subject_id": parts.get("subject_id"),
        "sample_id": sample_id,
        "sample_type": parts["type"],
        "material": parts["material"],
        "sample_source": parts.get("sample_source", "N/A"),
        "columns": columns,
    }


def ingest_taxprofiler(args):
    session, login_ms = get_session(args.url, args.username, args.password)
    check_case_available(session, args.url, args.case_id)

    classifiers = [parse_classifier(c) for c in args.classifier]
    classifier_names = [c["name"] for c in classifiers]
    _check_unique_classifier_names(classifier_names)
    samples = [parse_sample(s, classifier_names) for s in args.sample]
    _check_unique_sample_ids(samples)

    print(f"Building bundle for case '{args.case_id}' ({len(samples)} sample(s)) ...")
    with tempfile.TemporaryDirectory(prefix="ingest_cli_") as tmp:
        bundle_path = Path(tmp) / "bundle.tar.gz"
        t_build = _ms()
        build_taxprofiler_bundle(
            bundle_path,
            case_id=args.case_id,
            ticket_id=args.ticket_id,
            order_date=args.order_date,
            multiqc_path=args.multiqc,
            multiqc_report_path=args.multiqc_report,
            pipeline_info_path=args.pipeline_info,
            metaval_dir=args.metaval,
            classifiers=classifiers,
            samples=samples,
            analysis_type=args.analysis_type,
            sequencing_platform=args.sequencing_platform,
        )
        build_ms = _ms() - t_build
        size_mb = bundle_path.stat().st_size / (1024 * 1024)
        print(f"  Bundle        : {size_mb:.1f} MiB ({build_ms} ms)")

        print(f"Uploading bundle to {args.url} ...")
        t0 = _ms()
        with open(bundle_path, "rb") as fh:
            resp = session.post(
                f"{args.url}/api/v1/ingest/taxprofiler",
                files={"bundle": (bundle_path.name, fh, "application/gzip")},
            )
        api_ms = _ms() - t0

    _print_result(resp, args.case_id, login_ms=login_ms, api_ms=api_ms)


def _add_taxprofiler_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--ticket-id",
        default=None,
        help="Freshdesk ticket ID associated with this case (optional)",
    )
    parser.add_argument(
        "--order-date", default=None, help="Case order date (YYYY-MM-DD)"
    )
    parser.add_argument("--multiqc", required=True)
    parser.add_argument(
        "--multiqc-report",
        default=None,
        help="Path to multiqc_report.html (stored in object storage)",
    )
    parser.add_argument(
        "--pipeline-info",
        required=True,
        help="Path to nf_core_*_software_mqc_versions.yml file",
    )
    parser.add_argument(
        "--metaval",
        default=None,
        help="Path to metaval output root directory (optional)",
    )
    parser.add_argument(
        "--classifier",
        action="append",
        required=True,
        metavar="NAME db=DB taxpasta=PATH [krona=PATH]",
        help="Classifier descriptor. Repeat for each classifier.",
    )
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        metavar="KEY=VALUE ...",
        help="Sample descriptor. Repeat for each sample.",
    )
    parser.add_argument(
        "--analysis-type",
        choices=["shotgun", "amplicon"],
        default=None,
        help="Analysis type: shotgun (metagenomics) or amplicon (16S)",
    )
    parser.add_argument(
        "--sequencing-platform",
        choices=["illumina", "nanopore"],
        default=None,
        help="Sequencing platform: illumina or nanopore",
    )
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)


# ---------------------------------------------------------------------------
# Trana subcommand
# ---------------------------------------------------------------------------


def parse_trana_sample(raw: str) -> dict:
    parts = {}
    for token in raw.split():
        if "=" not in token:
            print(f"Invalid sample token '{token}' — expected key=value")
            sys.exit(1)
        k, v = token.split("=", 1)
        parts[k.strip()] = v.strip()

    required = {"sample_id", "type", "material", "abundance_path"}
    missing = required - parts.keys()
    if missing:
        print(f"Sample is missing required keys: {missing}")
        sys.exit(1)

    return {
        "subject_id": parts.get("subject_id"),
        "sample_id": parts["sample_id"],
        "sample_type": parts["type"],
        "material": parts["material"],
        "sample_source": parts.get("sample_source", "N/A"),
        "abundance_path": parts["abundance_path"],
        "krona_path": parts.get("krona_path"),
        "nanoplot_unprocessed_path": parts.get("nanoplot_unprocessed_path"),
        "nanoplot_processed_path": parts.get("nanoplot_processed_path"),
    }


def ingest_trana(args):
    session, login_ms = get_session(args.url, args.username, args.password)
    check_case_available(session, args.url, args.case_id)

    samples = [parse_trana_sample(s) for s in args.sample]
    _check_unique_sample_ids(samples)

    print(
        f"Building bundle for Trana case '{args.case_id}' "
        f"({len(samples)} sample(s)) ..."
    )
    with tempfile.TemporaryDirectory(prefix="ingest_cli_trana_") as tmp:
        bundle_path = Path(tmp) / "bundle.tar.gz"
        t_build = _ms()
        build_trana_bundle(
            bundle_path,
            case_id=args.case_id,
            ticket_id=args.ticket_id,
            order_date=args.order_date,
            multiqc_report_path=args.multiqc_report,
            pipeline_info_path=args.pipeline_info,
            samples=samples,
            analysis_type=args.analysis_type,
            sequencing_platform=args.sequencing_platform,
        )
        build_ms = _ms() - t_build
        size_mb = bundle_path.stat().st_size / (1024 * 1024)
        print(f"  Bundle        : {size_mb:.1f} MiB ({build_ms} ms)")

        print(f"Uploading bundle to {args.url} ...")
        t0 = _ms()
        with open(bundle_path, "rb") as fh:
            resp = session.post(
                f"{args.url}/api/v1/ingest/trana",
                files={"bundle": (bundle_path.name, fh, "application/gzip")},
            )
        api_ms = _ms() - t0

    _print_result(resp, args.case_id, login_ms=login_ms, api_ms=api_ms)


def _add_trana_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--ticket-id",
        default=None,
        help="Freshdesk ticket ID associated with this case (optional)",
    )
    parser.add_argument(
        "--order-date", default=None, help="Case order date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--pipeline-info",
        required=True,
        help="Path to Trana software_versions.yml",
    )
    parser.add_argument(
        "--multiqc-report",
        default=None,
        help="Path to multiqc_report.html (stored in object storage)",
    )
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        metavar="KEY=VALUE ...",
        help=(
            "Sample descriptor. Required: sample_id, type, material, abundance_path. "
            "Optional: subject_id, sample_source, krona_path, "
            "nanoplot_unprocessed_path, nanoplot_processed_path. "
            "Repeat for each sample."
        ),
    )
    parser.add_argument(
        "--analysis-type",
        choices=["shotgun", "amplicon"],
        default="amplicon",
        help="Analysis type (default: amplicon)",
    )
    parser.add_argument(
        "--sequencing-platform",
        choices=["illumina", "nanopore"],
        default="nanopore",
        help="Sequencing platform (default: nanopore)",
    )
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _print_result(
    resp: requests.Response,
    case_id: str,
    login_ms: int = 0,
    api_ms: int = 0,
) -> None:
    if resp.status_code == 200:
        result = resp.json()
        print(f"Ingested case '{result['case_id']}'")
        print(f"  Samples       : {result['samples_ingested']}")
        for sid in result["sample_ids"]:
            print(f"  Sample ID     : {sid}")
        print(
            f"  Timing        : login {login_ms}ms  api {api_ms}ms  "
            f"total {login_ms + api_ms}ms"
        )
    else:
        print(f"Ingest failed ({resp.status_code}): {resp.text}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_SUBCOMMANDS = {"taxprofiler", "trana"}


def main():
    # Backward compatibility: if first arg is not a subcommand, assume taxprofiler
    if len(sys.argv) > 1 and sys.argv[1] not in _SUBCOMMANDS and sys.argv[1] != "-h":
        sys.argv.insert(1, "taxprofiler")

    parser = argparse.ArgumentParser(
        description="Ingest pipeline results into meta-vis-app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    tp_parser = subparsers.add_parser(
        "taxprofiler", help="Ingest a taxprofiler (shotgun metagenomics) case"
    )
    _add_taxprofiler_args(tp_parser)

    tr_parser = subparsers.add_parser(
        "trana", help="Ingest a Trana (16S amplicon, ONT, Emu) case"
    )
    _add_trana_args(tr_parser)

    args = parser.parse_args()

    if args.command == "taxprofiler":
        ingest_taxprofiler(args)
    elif args.command == "trana":
        ingest_trana(args)


if __name__ == "__main__":
    main()
