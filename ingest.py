#!/usr/bin/env python
"""
Ingest a taxprofiler run into meta-vis-app.

Usage:
    python ingest.py \\
        --run-id run_2026_02_23 \\
        --subject-id S-001 \\
        --sample-id PE-04-28 \\
        --sample-type test \\
        --order-date 2026-02-20 \\
        --taxpasta /abs/path/to/taxpasta.tsv \\
        --taxpasta-column "PE-04-28_k2_pluspf.kraken2.kraken2.report" \\
        --classifier kraken2 \\
        --classifier-db k2_pluspf \\
        --multiqc /abs/path/to/multiqc_data.json \\
        --pipeline-info /abs/path/to/pipeline_info \\
        --url http://localhost:8000 \\
        --username admin \\
        --password yourpassword

For controls, pass --sample-type negative_ctrl or --sample-type positive_ctrl
and omit --subject-id (it will default to empty).

To ingest multiple samples in one run, call this script once per sample.
The script is idempotent for runs: if the run_id already exists in the DB
the ingest endpoint will create a second run document. Re-ingest after
dropping the collections if you need a clean slate.
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


def ingest(args):
    token = get_token(args.url, args.username, args.password)

    payload = {
        "run_id": args.run_id,
        "samples": [
            {
                "subject_id": args.subject_id or "",
                "sample_type": args.sample_type,
                "order_date": args.order_date,
                "taxpasta_path": args.taxpasta,
                "taxpasta_column": args.taxpasta_column,
                "classifier": args.classifier,
                "classifier_db": args.classifier_db,
                "multiqc_path": args.multiqc,
                "pipeline_info_path": args.pipeline_info,
                "krona_path": args.krona,
                "sample": {
                    "sample_id": args.sample_id,
                    "sample_source": args.sample_source,
                    "biopsy_id": args.biopsy_id,
                },
            }
        ],
    }

    resp = requests.post(
        f"{args.url}/api/v1/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"✓ Ingested run '{result['run_id']}'")
        print(f"  Run ObjectId : {result['run_object_id']}")
        print(f"  Samples      : {result['samples_ingested']}")
        for sid in result["sample_ids"]:
            print(f"  Sample ID    : {sid}")
    else:
        print(f"Ingest failed ({resp.status_code}): {resp.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Ingest a taxprofiler sample into meta-vis-app")

    # Run
    parser.add_argument("--run-id",         required=True,  help="Run identifier, e.g. run_2026_02_23")

    # Sample identity
    parser.add_argument("--subject-id",     default="",     help="Subject identifier, e.g. S-001")
    parser.add_argument("--sample-id",      required=True,  help="Sample identifier, e.g. PE-04-28")
    parser.add_argument("--sample-type",    default="test",
                        choices=["test", "negative_ctrl", "positive_ctrl"],
                        help="Sample type (default: test)")
    parser.add_argument("--order-date",     default=None,   help="ISO date when sample was submitted, e.g. 2026-02-20")
    parser.add_argument("--sample-source",  default=None,   help="Sample source tissue/site")
    parser.add_argument("--biopsy-id",      default=None,   help="Biopsy identifier")

    # Pipeline outputs
    parser.add_argument("--taxpasta",       required=True,  help="Path to TAXPASTA TSV file")
    parser.add_argument("--taxpasta-column",required=True,  help="Column name in TAXPASTA file for this sample")
    parser.add_argument("--classifier",     default="kraken2", help="Classifier used (default: kraken2)")
    parser.add_argument("--classifier-db",  default=None,   help="Classifier database name, e.g. k2_pluspf")
    parser.add_argument("--multiqc",        required=True,  help="Path to multiqc_data.json")
    parser.add_argument("--pipeline-info",  required=True,  help="Path to pipeline_info directory")
    parser.add_argument("--krona",          default=None,   help="Path to Krona HTML file (optional)")

    # Server / auth
    parser.add_argument("--url",      default="http://localhost:8000", help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--username", default="admin",  help="Username (default: admin)")
    parser.add_argument("--password", required=True,    help="Password")

    args = parser.parse_args()
    ingest(args)


if __name__ == "__main__":
    main()