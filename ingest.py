#!/usr/bin/env python
"""
Ingest a taxprofiler case into meta-vis-app.

One call per case. All samples in the case share the same taxpasta, multiqc,
pipeline_info, and (optionally) krona files. Each sample is described
explicitly with its taxpasta column, type, and material.

Usage:
    python ingest.py \
        --case-id case_2026_02_23 \
        --taxonomy-db k2_pluspf \
        --taxpasta /path/to/kraken2_k2_pluspf.tsv \
        --multiqc  /path/to/multiqc_data.json \
        --pipeline-info /path/to/pipeline_info \
        --krona    /path/to/kraken2_k2_pluspf.html \
        --sample "subject_id=S-001 sample_id=PE-04-28 column=PE-04-28_k2_pluspf.kraken2.kraken2.report type=test material=DNA order_date=2026-02-20" \
        --sample "subject_id=S-001 sample_id=EN-30-35 column=EN-30-35_k2_pluspf.kraken2.kraken2.report type=test material=RNA order_date=2026-02-20" \
        --sample "sample_id=H2-17-32 column=H2-17-32_k2_pluspf.kraken2.kraken2.report type=positive_ctrl material=DNA" \
        --sample "sample_id=VZ-20-28 column=VZ-20-28_k2_pluspf.kraken2.kraken2.report type=positive_ctrl material=RNA" \
        --password yourpassword
"""

import argparse
import sys
import requests


def get_token(base_url: str, username: str, password: str) -> str:
    resp = requests.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}")
        sys.exit(1)
    return resp.json()["access_token"]


def parse_sample(raw: str) -> dict:
    """
    Parse a --sample argument of the form:
      key=value key=value ...
    Recognised keys: subject_id, sample_id, column, type, material, order_date
    """
    parts = {}
    for token in raw.split():
        if "=" not in token:
            print(f"Invalid sample token '{token}' — expected key=value")
            sys.exit(1)
        k, v = token.split("=", 1)
        parts[k.strip()] = v.strip()

    required = {"sample_id", "column", "type", "material"}
    missing = required - parts.keys()
    if missing:
        print(f"Sample is missing required keys: {missing}")
        sys.exit(1)

    return {
        "subject_id":      parts.get("subject_id"),
        "sample_id":       parts["sample_id"],
        "taxpasta_column": parts["column"],
        "sample_type":     parts["type"],
        "material":        parts["material"],
        "order_date":      parts.get("order_date"),
    }


def ingest(args):
    token = get_token(args.url, args.username, args.password)

    samples = [parse_sample(s) for s in args.sample]

    payload = {
        "case_id":            args.case_id,
        "taxonomy_db":        args.taxonomy_db,
        "taxpasta_path":      args.taxpasta,
        "multiqc_path":       args.multiqc,
        "pipeline_info_path": args.pipeline_info,
        "krona_path":         args.krona,
        "samples":            samples,
    }

    print(f"Ingesting {len(samples)} sample(s) for case '{args.case_id}' ...")

    resp = requests.post(
        f"{args.url}/api/v1/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"✓ Ingested case '{result['case_id']}'")
        print(f"  Case ObjectId : {result['case_object_id']}")
        print(f"  Samples       : {result['samples_ingested']}")
        for sid in result["sample_ids"]:
            print(f"  Sample ID     : {sid}")
    else:
        print(f"Ingest failed ({resp.status_code}): {resp.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a taxprofiler case into meta-vis-app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Case-level
    parser.add_argument("--case-id",        required=True,  help="Case identifier, e.g. case_2026_02_23")
    parser.add_argument("--taxonomy-db",    default=None,   help="Name of a loaded taxonomy, e.g. k2_pluspf")

    # Shared pipeline outputs
    parser.add_argument("--taxpasta",       required=True,  help="Path to TAXPASTA TSV file (shared across all samples)")
    parser.add_argument("--multiqc",        required=True,  help="Path to multiqc_data.json (shared across all samples)")
    parser.add_argument("--pipeline-info",  required=True,  help="Path to pipeline_info directory (shared across all samples)")
    parser.add_argument("--krona",          default=None,   help="Path to Krona HTML file for the case (optional)")

    # Per-sample — repeat --sample for each sample in the case
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        metavar="KEY=VALUE ...",
        help=(
            "Sample descriptor as space-separated key=value pairs. "
            "Required keys: sample_id, column, type, material. "
            "Optional keys: subject_id, order_date. "
            "Repeat --sample for each sample in the case."
        ),
    )

    # Server / auth
    parser.add_argument("--url",      default="http://localhost:8000", help="API base URL")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)

    args = parser.parse_args()
    ingest(args)


if __name__ == "__main__":
    main()
