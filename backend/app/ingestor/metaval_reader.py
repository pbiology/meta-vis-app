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


def _read_blast(metaval_dir: Path) -> dict:
    """
    Scan blast/blastn/{classifier}/ for all summary files.
    Returns a dict keyed by (sample_name, classifier, taxon_name) -> list of hit dicts.
    Only reads *_blast_filtered_summary.txt files with content.
    """
    results = {}
    blastn_dir = metaval_dir / 'blast' / 'blastn'
    if not blastn_dir.exists():
        return results

    for clf_dir in blastn_dir.iterdir():
        if not clf_dir.is_dir():
            continue
        classifier = clf_dir.name

        for summary_file in clf_dir.glob('*_blast_filtered_summary.txt'):
            if summary_file.stat().st_size == 0:
                continue

            # filename: {sample_name}_{taxon_name}_blast_filtered_summary.txt
            stem = summary_file.stem  # e.g. SRR13439790_Shigella-virus-Moo19_blast_filtered_summary
            # strip trailing _blast_filtered_summary
            name_part = stem.replace('_blast_filtered_summary', '')
            # split on first underscore to get sample_name
            # sample names contain underscores too, so we need to match against known samples
            # store as full name_part and resolve later
            rows = []
            with open(summary_file) as f:
                lines = f.readlines()
            if len(lines) < 2:
                continue
            headers = lines[0].strip().split('\t')
            for line in lines[1:]:
                cols = line.strip().split('\t')
                if cols and len(cols) == len(headers):
                    rows.append(dict(zip(headers, cols)))

            results[(name_part, classifier)] = rows

    return results


def _read_metaval_pipeline_info(metaval_dir: Path) -> Optional[dict]:
    """
    Read the metaval software versions file from pipeline_info/.
    Returns the same structure as pipeline_info_reader.read_pipeline_info.
    """
    pipeline_info_dir = metaval_dir / 'pipeline_info'
    if not pipeline_info_dir.exists():
        return None
    versions_file = next(pipeline_info_dir.glob('*.yml'), None)
    if not versions_file:
        return None
    try:
        from app.ingestor.pipeline_info_reader import read_pipeline_info
        return read_pipeline_info(str(versions_file))
    except Exception:
        return None


def read_metaval(metaval_igv_dir: str) -> list[dict]:
    igv_dir     = Path(metaval_igv_dir)
    metaval_dir = igv_dir.parent

    if not igv_dir.exists():
        raise FileNotFoundError(f"Metaval IGV directory not found: {metaval_igv_dir}")

    taxid_map = _read_viral_taxids(metaval_dir)
    blast_data = _read_blast(metaval_dir)
    metaval_pipeline = _read_metaval_pipeline_info(metaval_dir)

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
        groups[key].append({
            'organism_name': parsed['organism_name'],
            'igv_file_path': str(html_file),
            'igv_file_size_bytes': file_size,
            'igv_too_large': too_large,
        })

    results = []
    for (sample_name, classifier, taxon_name), organisms in groups.items():
        taxon_id = taxid_map.get((classifier, taxon_name))

        # Match blast summary — name_part is "{sample_name}_{taxon_name}"
        name_part   = f"{sample_name}_{taxon_name}"
        blast_hits  = blast_data.get((name_part, classifier), [])

        results.append({
            'sample_name': sample_name,
            'classifier':  classifier,
            'taxon_id':    taxon_id,
            'taxon_name':  taxon_name,
            'organisms':   organisms,
            'blast':       blast_hits,
        })

    return {
        'results': results,
        'pipeline_info': metaval_pipeline,
    }
