#!/usr/bin/env python
"""
Ingest pipeline results into meta-vis-app.

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
"""

import argparse
import sys
import requests


def get_session(base_url: str, username: str, password: str) -> requests.Session:
    session = requests.Session()
    resp = session.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}")
        sys.exit(1)
    data = resp.json()
    print(f"Logged in as {data['username']} ({data['role']})")
    return session


# ---------------------------------------------------------------------------
# Taxprofiler subcommand
# ---------------------------------------------------------------------------


def parse_classifier(raw: str) -> dict:
    """
    Parse a --classifier argument of the form:
      kraken2 db=k2_pluspf taxpasta=/path/to/file.tsv krona=/path/to/file.html
    First token is the classifier name, rest are key=value pairs.
    """
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
    """
    Parse a --sample argument of the form:
      key=value key=value ...
    Required keys: sample_id, type, material
    Optional keys: subject_id, order_date
    Classifier columns: column_{classifier_name} for each classifier
    """
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

    columns = {}
    for clf_name in classifier_names:
        col_key = f"column_{clf_name}"
        if col_key in parts:
            columns[clf_name] = parts[col_key]

    return {
        "subject_id": parts.get("subject_id"),
        "sample_id": parts["sample_id"],
        "sample_type": parts["type"],
        "material": parts["material"],
        "sample_source": parts.get("sample_source", "N/A"),
        "columns": columns,
    }


def ingest_taxprofiler(args):
    session = get_session(args.url, args.username, args.password)

    classifiers = [parse_classifier(c) for c in args.classifier]
    classifier_names = [c["name"] for c in classifiers]
    samples = [parse_sample(s, classifier_names) for s in args.sample]

    payload = {
        "case_id": args.case_id,
        "order_date": args.order_date,
        "multiqc_path": args.multiqc,
        "multiqc_report_path": args.multiqc_report,
        "pipeline_info_path": args.pipeline_info,
        "classifiers": classifiers,
        "samples": samples,
        "metaval": {"metaval_dir": args.metaval} if args.metaval else None,
        "analysis_type": args.analysis_type,
        "sequencing_platform": args.sequencing_platform,
    }

    print(f"Ingesting {len(samples)} sample(s) for case '{args.case_id}' ...")

    resp = session.post(
        f"{args.url}/api/v1/ingest",
        json=payload,
    )

    _print_result(resp, args.case_id)


def _add_taxprofiler_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-id", required=True)
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
        help="Path to nf_core_*_software_mqc_versions.yml file (or legacy pipeline_info directory)",
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
    """
    Parse a --sample argument for Trana ingest.
    Required keys: sample_id, type, material, abundance_path
    Optional keys: subject_id, sample_source, krona_path,
                   nanoplot_unprocessed_path, nanoplot_processed_path
    """
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
    session = get_session(args.url, args.username, args.password)

    samples = [parse_trana_sample(s) for s in args.sample]

    payload = {
        "case_id": args.case_id,
        "order_date": args.order_date,
        "multiqc_report_path": args.multiqc_report,
        "pipeline_info_path": args.pipeline_info,
        "samples": samples,
        "analysis_type": args.analysis_type,
        "sequencing_platform": args.sequencing_platform,
    }

    print(f"Ingesting {len(samples)} Trana sample(s) for case '{args.case_id}' ...")

    resp = session.post(
        f"{args.url}/api/v1/ingest/trana",
        json=payload,
    )

    _print_result(resp, args.case_id)


def _add_trana_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-id", required=True)
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


def _print_result(resp: requests.Response, case_id: str) -> None:
    if resp.status_code == 200:
        result = resp.json()
        print(f"Ingested case '{result['case_id']}'")
        print(f"  Case ObjectId : {result['case_object_id']}")
        print(f"  Samples       : {result['samples_ingested']}")
        for sid in result["sample_ids"]:
            print(f"  Sample ID     : {sid}")
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
