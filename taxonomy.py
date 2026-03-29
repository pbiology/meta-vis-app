#!/usr/bin/env python
"""
Load an NCBI taxonomy into meta-vis-app as a versioned reference.

Requires both nodes.dmp and names.dmp from the same NCBI taxonomy dump.
These are found in the taxonomy/ subdirectory of any Kraken2 database,
or can be downloaded directly from NCBI.

Usage:
    python taxonomy.py \
        --nodes-data /path/to/taxonomy/nodes.dmp \
        --names-data /path/to/taxonomy/names.dmp \
        --name k2_pluspf \
        --date 2024-11-01 \
        --url http://localhost:8000 \
        --username admin \
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


def read_lines(path: str) -> list[str]:
    print(f"Reading {path} ...")
    with open(path) as fh:
        lines = fh.readlines()
    print(f"  {len(lines):,} lines read.")
    return [l.rstrip("\n") for l in lines]


def load(args):
    token = get_token(args.url, args.username, args.password)

    nodes_raw = read_lines(args.nodes_data)
    names_raw = read_lines(args.names_data)

    print("Uploading to API (this may take several minutes) ...")

    resp = requests.post(
        f"{args.url}/api/v1/taxonomy/load",
        json={
            "name":               args.name,
            "ncbi_taxonomy_date": args.date,
            "nodes_raw":          nodes_raw,
            "names_raw":          names_raw,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=600,
    )

    if resp.status_code == 200:
        result = resp.json()
        print(f"✓ Loaded taxonomy '{result['name']}'")
        print(f"  Taxonomy ID : {result['taxonomy_db_id']}")
        print(f"  NCBI date   : {result['ncbi_taxonomy_date']}")
        print(f"  Node count  : {result['node_count']:,}")
    else:
        print(f"Load failed ({resp.status_code}): {resp.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Load NCBI taxonomy into meta-vis-app"
    )
    parser.add_argument("--nodes-data", required=True, help="Path to nodes.dmp")
    parser.add_argument("--names-data", required=True, help="Path to names.dmp")
    parser.add_argument("--name",       required=True, help="Taxonomy name, e.g. k2_pluspf")
    parser.add_argument("--date",       required=True, help="NCBI taxonomy date, e.g. 2024-11-01")
    parser.add_argument("--url",        default="http://localhost:8000")
    parser.add_argument("--username",   default="admin")
    parser.add_argument("--password",   required=True)
    args = parser.parse_args()
    load(args)


if __name__ == "__main__":
    main()