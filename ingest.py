#!/usr/bin/env python
"""
Ingest a taxprofiler case into meta-vis-app.

Usage:
    python ingest.py \
        --case-id slowtiger \
        --taxonomy-db k2_pluspf \
        --multiqc  /path/to/multiqc_data.json \
        --pipeline-info /path/to/pipeline_info \
        --classifier "kraken2 db=k2_pluspf taxpasta=/path/kraken2.tsv krona=/path/kraken2.html" \
        --classifier "centrifuge db=p_compressed+h+v taxpasta=/path/centrifuge.tsv krona=/path/centrifuge.html" \
        --sample "subject_id=S-001 sample_id=PE-04-28 type=sample material=DNA order_date=2026-02-20 column_kraken2=PE-04-28_k2_pluspf.kraken2.kraken2.report column_centrifuge=PE-04-28_p_compressed+h+v.centrifuge" \
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
        "name":    name,
        "db":      parts["db"],
        "taxpasta": parts["taxpasta"],
        "krona":   parts.get("krona"),
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


def ingest(args):
    token = get_token(args.url, args.username, args.password)

    classifiers = [parse_classifier(c) for c in args.classifier]
    classifier_names = [c["name"] for c in classifiers]
    samples = [parse_sample(s, classifier_names) for s in args.sample]

    payload = {
        "case_id": args.case_id,
        "order_date": args.order_date,
        "multiqc_path": args.multiqc,
        "pipeline_info_path": args.pipeline_info,
        "classifiers": classifiers,
        "samples": samples,
        "metaval": {"igv_dir": args.metaval_igv} if args.metaval_igv else None,
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
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--order-date", default=None, help="Case order date (YYYY-MM-DD)")
    parser.add_argument("--multiqc", required=True)
    parser.add_argument("--pipeline-info", required=True,
                        help="Path to nf_core_*_software_mqc_versions.yml file (or legacy pipeline_info directory)")
    parser.add_argument("--metaval-igv", default=None, help="Path to metaval igv/ directory (optional)")
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
    parser.add_argument("--url",      default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)

    args = parser.parse_args()
    ingest(args)


if __name__ == "__main__":
    main()