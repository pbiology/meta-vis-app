# app/ingestor/metaval_reader.py

import os
import re
from pathlib import Path
from typing import Optional


MAX_IGV_SIZE = 10 * 1024 * 1024  # 10 MB


def _parse_igv_filename(filename: str) -> Optional[dict]:
    """
    Parse an IGV report filename into its components.
    Pattern: {sample_name}_{classifier}_{taxon_name}_mappingorganism_{organism_name}_report.html
    """
    pattern = r'^(.+?)_(kraken2|centrifuge|diamond)_(.+?)_mappingorganism_(.+?)_report\.html$'
    m = re.match(pattern, filename)
    if not m:
        return None
    return {
        'sample_name':    m.group(1),
        'classifier':     m.group(2),
        'taxon_name':     m.group(3),
        'organism_name':  m.group(4),
    }


def _read_viral_taxids(metaval_dir: Path) -> dict:
    """
    Read all viral_taxids TSV files and return a dict of
    {(classifier, taxon_name): taxon_id}
    """
    taxid_map = {}
    taxids_dir = metaval_dir / 'viral_taxids'
    if not taxids_dir.exists():
        return taxid_map

    for tsv_file in taxids_dir.glob('*_viral_taxids.tsv'):
        # filename: {sample_name}_{classifier}_viral_taxids.tsv
        stem = tsv_file.stem  # e.g. SRR13439790_kraken2_viral_taxids
        parts = stem.split('_')
        # find classifier
        clf = None
        for c in ['kraken2', 'centrifuge', 'diamond']:
            if c in parts:
                clf = c
                break
        if not clf:
            continue
        with open(tsv_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                cols = line.split('\t')
                if len(cols) >= 2:
                    try:
                        taxon_id   = int(cols[0])
                        taxon_name = cols[1].strip()
                        taxid_map[(clf, taxon_name)] = taxon_id
                    except ValueError:
                        continue
    return taxid_map


def _read_blast(metaval_dir: Path, sample_name: str, classifier: str, taxon_name: str) -> dict:
    """
    Read blast filtered hits and summary for a given sample/classifier/taxon.
    Returns {'hits': [...], 'summary': [...]} or empty dicts if not found.
    """
    result = {'hits': [], 'summary': []}

    for blast_type in ['blastn', 'blastx']:
        blast_dir = metaval_dir / 'blast' / blast_type / classifier
        if not blast_dir.exists():
            continue

        filtered_file = blast_dir / f'{sample_name}_{taxon_name}_blast_filtered.txt'
        summary_file  = blast_dir / f'{sample_name}_{taxon_name}_blast_filtered_summary.txt'

        if filtered_file.exists() and blast_type == 'blastn':
            rows = []
            with open(filtered_file) as f:
                lines = f.readlines()
            if lines:
                headers = lines[0].strip().split('\t')
                for line in lines[1:]:
                    cols = line.strip().split('\t')
                    if cols:
                        rows.append(dict(zip(headers, cols)))
            result['hits'] = rows

        if summary_file.exists() and blast_type == 'blastn':
            rows = []
            with open(summary_file) as f:
                lines = f.readlines()
            if lines:
                headers = lines[0].strip().split('\t')
                for line in lines[1:]:
                    cols = line.strip().split('\t')
                    if cols:
                        rows.append(dict(zip(headers, cols)))
            result['summary'] = rows

    return result


def read_metaval(metaval_igv_dir: str) -> list[dict]:
    """
    Scan the metaval IGV directory and return a list of metaval result dicts,
    one per (sample_name, classifier, taxon_name) combination.

    Each dict:
    {
        sample_name: str,
        classifier: str,
        taxon_id: int | None,
        taxon_name: str,
        organisms: [
            {
                organism_name: str,
                igv_html: str | None,
                igv_file_size_bytes: int,
                igv_too_large: bool,
            }
        ],
        blast: { hits: [...], summary: [...] }
    }
    """
    igv_dir    = Path(metaval_igv_dir)
    metaval_dir = igv_dir.parent  # assume igv/ is directly under metaval root

    if not igv_dir.exists():
        raise FileNotFoundError(f"Metaval IGV directory not found: {metaval_igv_dir}")

    taxid_map = _read_viral_taxids(metaval_dir)

    # Group IGV files by (sample_name, classifier, taxon_name)
    groups: dict[tuple, list] = {}
    for html_file in sorted(igv_dir.glob('*_report.html')):
        parsed = _parse_igv_filename(html_file.name)
        if not parsed:
            continue

        key = (parsed['sample_name'], parsed['classifier'], parsed['taxon_name'])
        if key not in groups:
            groups[key] = []

        file_size = html_file.stat().st_size
        too_large = file_size > MAX_IGV_SIZE

        igv_html = None
        if not too_large:
            igv_html = html_file.read_text(encoding='utf-8')

        groups[key].append({
            'organism_name':      parsed['organism_name'],
            'igv_html':           igv_html,
            'igv_file_size_bytes': file_size,
            'igv_too_large':      too_large,
        })

    results = []
    for (sample_name, classifier, taxon_name), organisms in groups.items():
        taxon_id = taxid_map.get((classifier, taxon_name))
        blast    = _read_blast(metaval_dir, sample_name, classifier, taxon_name)
        results.append({
            'sample_name': sample_name,
            'classifier':  classifier,
            'taxon_id':    taxon_id,
            'taxon_name':  taxon_name,
            'organisms':   organisms,
            'blast':       blast,
        })

    return results