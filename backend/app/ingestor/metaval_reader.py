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
    Scan blast/blastn/ and blast/blastx/ for summary files.
    Returns a dict keyed by (name_part, classifier) ->
      {'blastn': [...rows], 'blastx': [...rows]}
    where name_part is "{sample_name}_{taxon_name}".
    Only reads *_filtered_summary.txt files with content.
    """
    results: dict[tuple, dict] = {}

    for program in ('blastn', 'blastx'):
        program_dir = metaval_dir / 'blast' / program
        if not program_dir.exists():
            continue

        suffix = f'_blast_filtered_summary.txt' if program == 'blastn' else f'_blastx_filtered_summary.txt'

        for clf_dir in program_dir.iterdir():
            if not clf_dir.is_dir():
                continue
            classifier = clf_dir.name

            for summary_file in clf_dir.glob(f'*{suffix}'):
                if summary_file.stat().st_size == 0:
                    continue
                stem      = summary_file.stem
                name_part = stem.replace(f'_blast_filtered_summary' if program == 'blastn' else f'_blastx_filtered_summary', '')

                with open(summary_file) as f:
                    lines = f.readlines()
                if len(lines) < 2:
                    continue
                headers = lines[0].strip().split('\t')
                rows = []
                for line in lines[1:]:
                    cols = line.strip().split('\t')
                    if cols and len(cols) == len(headers):
                        rows.append(dict(zip(headers, cols)))

                key = (name_part, classifier)
                if key not in results:
                    results[key] = {'blastn': [], 'blastx': []}
                results[key][program] = rows

    return results


def _fasta_stats(path: Path) -> dict:
    """
    Compute sequence count and average length for a FASTA file.
    """
    sequences = []
    current_len = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if current_len > 0:
                    sequences.append(current_len)
                current_len = 0
            else:
                current_len += len(line)
    if current_len > 0:
        sequences.append(current_len)
    count = len(sequences)
    avg   = round(sum(sequences) / count, 1) if count else 0
    return {'count': count, 'avg_length': avg}


def _read_extracted_reads(metaval_dir: Path) -> dict:
    """
    Scan extracted_reads/{classifier}/ for paired FASTA files.
    Returns a dict keyed by (name_part, classifier) ->
      {'read_1_path': str, 'read_2_path': str | None, 'count': int, 'avg_length': float}
    where name_part is "{sample_name}_{taxon_name}" (same convention as blast).

    Filename pattern:
      {sample_name}_{taxon_name}.extracted_{classifier}_read_{1|2}.fa
    """
    reads_map = {}
    reads_dir = metaval_dir / 'extracted_reads'
    if not reads_dir.exists():
        return reads_map

    for clf_dir in reads_dir.iterdir():
        if not clf_dir.is_dir():
            continue
        classifier = clf_dir.name

        for fa_file in clf_dir.glob(f'*.extracted_{classifier}_read_1.fa'):
            name_part = fa_file.name.replace(f'.extracted_{classifier}_read_1.fa', '')
            read_2 = clf_dir / fa_file.name.replace('_read_1.fa', '_read_2.fa')
            read_2_path = str(read_2) if read_2.exists() else None
            stats = _fasta_stats(fa_file)
            reads_map[(name_part, classifier)] = {
                'read_1_path': str(fa_file),
                'read_2_path': read_2_path,
                'file_count': 2 if read_2_path else 1,
                'count': stats['count'],
                'avg_length': stats['avg_length'],
            }

    return reads_map


def _read_spades(metaval_dir: Path) -> dict:
    """
    Scan spades/{classifier}/ for assembly output.
    Prefers scaffolds.fa over contigs.fa.
    Returns a dict keyed by (name_part, classifier) ->
      {'type': 'scaffolds'|'contigs', 'path': str, 'count': int, 'avg_length': float}
    where name_part is "{sample_name}_{taxon_name}".

    Filename pattern:
      {sample_name}_{taxon_name}.scaffolds.fa
      {sample_name}_{taxon_name}.contigs.fa
    """
    spades_map = {}
    spades_dir = metaval_dir / 'spades'
    if not spades_dir.exists():
        return spades_map

    for clf_dir in spades_dir.iterdir():
        if not clf_dir.is_dir():
            continue
        classifier = clf_dir.name

        # Index available files by name_part
        scaffolds = {
            f.name.replace('.scaffolds.fa', ''): f
            for f in clf_dir.glob('*.scaffolds.fa')
        }
        contigs = {
            f.name.replace('.contigs.fa', ''): f
            for f in clf_dir.glob('*.contigs.fa')
        }

        all_name_parts = set(scaffolds) | set(contigs)
        for name_part in all_name_parts:
            if name_part in scaffolds:
                fa_file    = scaffolds[name_part]
                entry_type = 'scaffolds'
            else:
                fa_file    = contigs[name_part]
                entry_type = 'contigs'
            stats = _fasta_stats(fa_file)
            spades_map[(name_part, classifier)] = {
                'type':       entry_type,
                'path':       str(fa_file),
                'count':      stats['count'],
                'avg_length': stats['avg_length'],
            }

    return spades_map


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


def read_metaval(metaval_dir: str) -> dict:
    metaval_dir = Path(metaval_dir)
    igv_dir     = metaval_dir / 'igv'

    if not metaval_dir.exists():
        raise FileNotFoundError(f"Metaval directory not found: {metaval_dir}")
    if not igv_dir.exists():
        raise FileNotFoundError(f"Metaval igv/ subdirectory not found: {igv_dir}")

    taxid_map = _read_viral_taxids(metaval_dir)
    blast_data = _read_blast(metaval_dir)
    reads_data = _read_extracted_reads(metaval_dir)
    spades_data = _read_spades(metaval_dir)
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
            'organism_name':       parsed['organism_name'],
            'igv_file_path':       str(html_file),
            'igv_file_size_bytes': file_size,
            'igv_too_large':       too_large,
        })

    results = []
    for (sample_name, classifier, taxon_name), organisms in groups.items():
        taxon_id  = taxid_map.get((classifier, taxon_name))
        name_part = f"{sample_name}_{taxon_name}"

        blast_hits = blast_data.get((name_part, classifier), {'blastn': [], 'blastx': []})

        # Prefer spades assembly over raw reads if available
        spades = spades_data.get((name_part, classifier))
        reads = reads_data.get((name_part, classifier), {})
        if spades:
            verification_data = {
                'type': spades['type'],  # 'scaffolds' or 'contigs'
                'path': spades['path'],
                'count': spades['count'],
                'avg_length': spades['avg_length'],
            }
        else:
            verification_data = {
                'type': 'raw_reads',
                'read_1_path': reads.get('read_1_path'),
                'read_2_path': reads.get('read_2_path'),
                'file_count': reads.get('file_count', 1),
                'count': reads.get('count', 0),
                'avg_length': reads.get('avg_length', 0),
            }

        results.append({
            'sample_name': sample_name,
            'classifier': classifier,
            'taxon_id': taxon_id,
            'taxon_name': taxon_name,
            'organisms': organisms,
            'blast': blast_hits,
            'verification_data': verification_data,
        })

    return {
        'results':       results,
        'pipeline_info': metaval_pipeline,
    }