# app/ingestor/metaval_reader.py

import re
from pathlib import Path
from typing import Optional

from app.ingestor.models import (
    BlastHits,
    IgvOrganism,
    MetavalOutput,
    MetavalResult,
    PipelineInfoOutput,
    VerificationData,
)


MAX_IGV_SIZE = 10 * 1024 * 1024  # 10 MB


def _parse_igv_filename(filename: str) -> Optional[dict[str, str | int | None]]:
    """
    Parse an IGV report filename into its components.

    Supports two formats:
      Old: {sample}_{classifier}_{taxon_name}_mappingorganism_{organism_name}_report.html
      New: {sample}_{classifier}_taxid_{id}_{taxon_name}_mappingorganism_{organism_name}_report.html

    When the new format is detected, taxon_id_from_filename is set to the embedded int;
    otherwise it is None.
    """
    pattern = (
        r"^(.+?)_(kraken2|centrifuge|diamond)_(.+?)_mappingorganism_(.+?)_report\.html$"
    )
    m = re.match(pattern, filename)
    if not m:
        return None
    taxon_name = m.group(3)
    taxon_id_from_filename: Optional[int] = None
    taxid_m = re.match(r"^taxid_(\d+)_", taxon_name)
    if taxid_m:
        taxon_id_from_filename = int(taxid_m.group(1))
    return {
        "sample_name": m.group(1),
        "classifier": m.group(2),
        "taxon_name": taxon_name,
        "organism_name": m.group(4),
        "taxon_id_from_filename": taxon_id_from_filename,
    }


def _read_viral_taxids(metaval_dir: Path) -> dict[tuple[str, str], int]:
    """
    Read all viral_taxids TSV files and return a dict of
    {(classifier, taxon_name): taxon_id}
    """
    taxid_map: dict[tuple[str, str], int] = {}
    taxids_dir = metaval_dir / "viral_taxids"
    if not taxids_dir.exists():
        return taxid_map

    for tsv_file in taxids_dir.glob("*_viral_taxids.tsv"):
        stem = tsv_file.stem  # e.g. SRR13439790_kraken2_viral_taxids
        parts = stem.split("_")
        clf: Optional[str] = None
        for c in ["kraken2", "centrifuge", "diamond"]:
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
                cols = line.split("\t")
                if len(cols) >= 2:
                    try:
                        taxon_id = int(cols[0])
                        taxon_name = cols[1].strip()
                        taxid_map[(clf, taxon_name)] = taxon_id
                    except ValueError:
                        continue
    return taxid_map


def _read_blast(
    metaval_dir: Path,
) -> dict[tuple[str, str], dict[str, list[dict[str, str]]]]:
    """
    Scan blast/blastn/ and blast/blastx/ for summary files.
    Returns a dict keyed by (name_part, classifier) ->
      {'blastn': [...rows], 'blastx': [...rows]}
    Only reads *_filtered_summary.txt files with content.
    """
    results: dict[tuple[str, str], dict[str, list[dict[str, str]]]] = {}

    for program in ("blastn", "blastx"):
        program_dir = metaval_dir / "blast" / program
        if not program_dir.exists():
            continue

        suffix = (
            "_blast_filtered_summary.txt"
            if program == "blastn"
            else "_blastx_filtered_summary.txt"
        )

        for clf_dir in program_dir.iterdir():
            if not clf_dir.is_dir():
                continue
            classifier = clf_dir.name

            for summary_file in clf_dir.glob(f"*{suffix}"):
                if summary_file.stat().st_size == 0:
                    continue
                stem = summary_file.stem
                name_part = stem.replace(
                    "_blast_filtered_summary"
                    if program == "blastn"
                    else "_blastx_filtered_summary",
                    "",
                )

                with open(summary_file) as f:
                    lines = f.readlines()
                if len(lines) < 2:
                    continue
                headers = lines[0].strip().split("\t")
                rows: list[dict[str, str]] = []
                for line in lines[1:]:
                    cols = line.strip().split("\t")
                    if cols and len(cols) == len(headers):
                        rows.append(dict(zip(headers, cols)))

                key = (name_part, classifier)
                if key not in results:
                    results[key] = {"blastn": [], "blastx": []}
                results[key][program] = rows

    return results


def _fasta_stats(path: Path) -> dict[str, int | float]:
    """
    Compute sequence count and average length for a FASTA file.
    """
    sequences: list[int] = []
    current_len = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if current_len > 0:
                    sequences.append(current_len)
                current_len = 0
            else:
                current_len += len(line)
    if current_len > 0:
        sequences.append(current_len)
    count = len(sequences)
    avg = round(sum(sequences) / count, 1) if count else 0
    return {"count": count, "avg_length": avg}


def _read_extracted_reads(
    metaval_dir: Path,
) -> dict[tuple[str, str], dict[str, object]]:
    """
    Scan extracted_reads/{classifier}/ for paired FASTA files.
    Returns intermediate dicts keyed by (name_part, classifier).
    """
    reads_map: dict[tuple[str, str], dict[str, object]] = {}
    reads_dir = metaval_dir / "extracted_reads"
    if not reads_dir.exists():
        return reads_map

    for clf_dir in reads_dir.iterdir():
        if not clf_dir.is_dir():
            continue
        classifier = clf_dir.name

        for fa_file in clf_dir.glob(f"*.extracted_{classifier}_read_1.fa"):
            name_part = fa_file.name.replace(f".extracted_{classifier}_read_1.fa", "")
            read_2 = clf_dir / fa_file.name.replace("_read_1.fa", "_read_2.fa")
            read_2_path: Optional[str] = str(read_2) if read_2.exists() else None
            stats = _fasta_stats(fa_file)
            reads_map[(name_part, classifier)] = {
                "read_1_path": str(fa_file),
                "read_2_path": read_2_path,
                "file_count": 2 if read_2_path else 1,
                "count": stats["count"],
                "avg_length": stats["avg_length"],
            }

    return reads_map


def _read_spades(metaval_dir: Path) -> dict[tuple[str, str], dict[str, object]]:
    """
    Scan spades/{classifier}/ for assembly output.
    Prefers scaffolds.fa over contigs.fa.
    Returns intermediate dicts keyed by (name_part, classifier).
    """
    spades_map: dict[tuple[str, str], dict[str, object]] = {}
    spades_dir = metaval_dir / "spades"
    if not spades_dir.exists():
        return spades_map

    for clf_dir in spades_dir.iterdir():
        if not clf_dir.is_dir():
            continue
        classifier = clf_dir.name

        scaffolds = {
            f.name.replace(".scaffolds.fa", ""): f
            for f in clf_dir.glob("*.scaffolds.fa")
        }
        contigs = {
            f.name.replace(".contigs.fa", ""): f for f in clf_dir.glob("*.contigs.fa")
        }

        all_name_parts = set(scaffolds) | set(contigs)
        for name_part in all_name_parts:
            if name_part in scaffolds:
                fa_file = scaffolds[name_part]
                entry_type = "scaffolds"
            else:
                fa_file = contigs[name_part]
                entry_type = "contigs"
            stats = _fasta_stats(fa_file)
            spades_map[(name_part, classifier)] = {
                "type": entry_type,
                "path": str(fa_file),
                "count": stats["count"],
                "avg_length": stats["avg_length"],
            }

    return spades_map


def _read_metaval_pipeline_info(metaval_dir: Path) -> Optional[PipelineInfoOutput]:
    """
    Read the metaval software versions file from pipeline_info/.
    Returns a PipelineInfoOutput or None if the file is absent or invalid.
    """
    pipeline_info_dir = metaval_dir / "pipeline_info"
    if not pipeline_info_dir.exists():
        return None
    versions_file = next(pipeline_info_dir.glob("*.yml"), None)
    if not versions_file:
        return None
    try:
        from app.ingestor.pipeline_info_reader import read_pipeline_info

        return read_pipeline_info(str(versions_file))
    except Exception:
        return None


def read_metaval(metaval_dir: str) -> MetavalOutput:
    metaval_path = Path(metaval_dir)
    igv_dir = metaval_path / "igv"

    if not metaval_path.exists():
        raise FileNotFoundError(f"Metaval directory not found: {metaval_dir}")
    if not igv_dir.exists():
        raise FileNotFoundError(f"Metaval igv/ subdirectory not found: {igv_dir}")

    taxid_map = _read_viral_taxids(metaval_path)
    blast_data = _read_blast(metaval_path)
    reads_data = _read_extracted_reads(metaval_path)
    spades_data = _read_spades(metaval_path)
    metaval_pipeline = _read_metaval_pipeline_info(metaval_path)

    # Group IGV files by (sample_name, classifier, taxon_name)
    groups: dict[tuple[str, str, str], list[IgvOrganism]] = {}
    taxon_ids_from_filename: dict[tuple[str, str, str], int] = {}
    for html_file in sorted(igv_dir.glob("*_report.html")):
        parsed = _parse_igv_filename(html_file.name)
        if not parsed:
            continue
        key = (
            str(parsed["sample_name"]),
            str(parsed["classifier"]),
            str(parsed["taxon_name"]),
        )
        if key not in groups:
            groups[key] = []
            if parsed["taxon_id_from_filename"] is not None:
                taxon_ids_from_filename[key] = int(
                    parsed["taxon_id_from_filename"]
                )  # always int when not None, set by _parse_igv_filename
        file_size = html_file.stat().st_size
        groups[key].append(
            IgvOrganism(
                organism_name=str(parsed["organism_name"]),
                igv_file_path=str(html_file),
                igv_file_size_bytes=file_size,
                igv_too_large=file_size > MAX_IGV_SIZE,
            )
        )

    results: list[MetavalResult] = []
    for (sample_name, classifier, taxon_name), organisms in groups.items():
        # Prefer taxon_id embedded in the filename (new metaval format);
        # fall back to viral_taxids lookup for old-format files.
        taxon_id: Optional[int] = taxon_ids_from_filename.get(
            (sample_name, classifier, taxon_name)
        )
        if taxon_id is None:
            taxon_id = taxid_map.get((classifier, taxon_name))
        name_part = f"{sample_name}_{taxon_name}"

        raw_blast = blast_data.get(
            (name_part, classifier), {"blastn": [], "blastx": []}
        )
        blast_hits = BlastHits(
            blastn=raw_blast["blastn"],
            blastx=raw_blast["blastx"],
        )

        spades = spades_data.get((name_part, classifier))
        reads = reads_data.get((name_part, classifier), {})

        if spades:
            spades_count = spades["count"]
            spades_avg = spades["avg_length"]
            assert isinstance(spades_count, (int, float))
            assert isinstance(spades_avg, (int, float))
            verification_data = VerificationData(
                type=str(spades["type"]),
                path=str(spades["path"]),
                count=int(spades_count),
                avg_length=float(spades_avg),
            )
        else:
            reads_count = reads.get("count", 0)
            reads_avg = reads.get("avg_length", 0)
            reads_file_count = reads.get("file_count")
            assert isinstance(reads_count, (int, float))
            assert isinstance(reads_avg, (int, float))
            verification_data = VerificationData(
                type="raw_reads",
                read_1_path=str(reads["read_1_path"])
                if reads.get("read_1_path")
                else None,
                read_2_path=str(reads["read_2_path"])
                if reads.get("read_2_path")
                else None,
                file_count=int(reads_file_count)
                if isinstance(reads_file_count, (int, float))
                else 1,
                count=int(reads_count),
                avg_length=float(reads_avg),
            )

        results.append(
            MetavalResult(
                sample_name=sample_name,
                classifier=classifier,
                taxon_id=taxon_id,
                taxon_name=taxon_name,
                organisms=organisms,
                blast=blast_hits,
                verification_data=verification_data,
            )
        )

    return MetavalOutput(results=results, pipeline_info=metaval_pipeline)
