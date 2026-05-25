# app/ingestor/loader.py
"""Loader layer for the ingest pipeline.

The CLI uploads a tar.gz bundle to the server. The loader is the only place
that touches the filesystem on the server side: it safely extracts the bundle
into a TemporaryDirectory, parses every referenced file into typed content
via the existing reader modules, and returns ``(meta, inputs)`` ready for the
orchestrator. The orchestrator never sees user-supplied paths.

Bundle layout (taxprofiler)::

    manifest.json                                  # TaxprofilerIngestMeta as JSON
    multiqc/multiqc_data.json                      # required
    multiqc_report/<filename>                      # optional
    pipeline_info/<filename>                       # required
    classifiers/<name>/taxpasta/<filename>         # required per classifier
    classifiers/<name>/krona/<filename>            # optional per classifier
    metaval/<full subtree>                         # optional

Bundle layout (trana)::

    manifest.json                                  # TranaIngestMeta as JSON
    multiqc_report/<filename>                      # optional
    pipeline_info/<filename>                       # required
    samples/<sample_id>/abundance.tsv              # required per sample
    samples/<sample_id>/krona.html                 # optional per sample
    samples/<sample_id>/nanoplot_unprocessed/NanoStats.txt  # optional
    samples/<sample_id>/nanoplot_processed/NanoStats.txt    # optional
"""

from __future__ import annotations

import asyncio
import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

from app.config import settings
from app.ingestor.emu_reader import read_emu_abundance
from app.ingestor.metaval_reader import read_metaval
from app.ingestor.multiqc_reader import read_multiqc
from app.ingestor.models import (
    TaxprofilerIngestInputs,
    MultiQCRaw,
    PipelineInfoOutput,
    TranaIngestInputs,
    TranaSampleInputs,
)
from app.ingestor.nanoplot_reader import read_nanostats
from app.ingestor.pipeline_info_reader import read_pipeline_info
from app.ingestor.taxpasta_reader import load_taxpasta
from app.models.sample import TaxprofilerIngestMeta, TranaIngestMeta


# ---------------------------------------------------------------------------
# Arcname constants — shared with the CLI (it imports these so the two ends
# cannot drift). Keep this section as the canonical layout reference.
# ---------------------------------------------------------------------------

MANIFEST_ARC = "manifest.json"
MULTIQC_ARC = "multiqc/multiqc_data.json"
MULTIQC_REPORT_DIR = "multiqc_report"
PIPELINE_INFO_DIR = "pipeline_info"
CLASSIFIERS_DIR = "classifiers"
METAVAL_DIR = "metaval"
SAMPLES_DIR = "samples"


def classifier_taxpasta_arcname(name: str, basename: str) -> str:
    return f"{CLASSIFIERS_DIR}/{name}/taxpasta/{basename}"


def classifier_krona_arcname(name: str, basename: str) -> str:
    return f"{CLASSIFIERS_DIR}/{name}/krona/{basename}"


def classifier_taxpasta_dir(name: str) -> str:
    return f"{CLASSIFIERS_DIR}/{name}/taxpasta"


def classifier_krona_dir(name: str) -> str:
    return f"{CLASSIFIERS_DIR}/{name}/krona"


def sample_dir(sample_id: str) -> str:
    return f"{SAMPLES_DIR}/{sample_id}"


# ---------------------------------------------------------------------------
# Bundle extraction
# ---------------------------------------------------------------------------


class BundleError(Exception):
    """Raised when a bundle is malformed, unsafe, or inconsistent with its
    manifest. Routers translate this to HTTP 400."""


class BundleTooLargeError(Exception):
    """Raised when a bundle exceeds the configured size cap. Routers translate
    this to HTTP 413."""


def _open_tar(source: BinaryIO | Path) -> tarfile.TarFile:
    """Open a tar in the right mode: random-access for Path, streaming for
    file-like (no seek required, used when streaming from an UploadFile)."""
    if isinstance(source, Path):
        return tarfile.open(source, mode="r:*")
    return tarfile.open(fileobj=source, mode="r|*")


def _safe_extract(
    source: BinaryIO | Path, dest_dir: Path, max_uncompressed: int
) -> None:
    """Extract a tar stream into ``dest_dir`` safely.

    Security is delegated to Python 3.12+'s PEP 706 ``data`` extraction
    filter, which rejects absolute paths, ``..`` traversal, symlinks,
    hardlinks, device nodes, and sets safe permissions. On top of that we
    enforce a configurable uncompressed-size cap (the filter doesn't bound
    total size — tar bombs would otherwise extract until the disk fills).
    """
    total = 0
    with _open_tar(source) as tar:
        for member in tar:
            if member.isreg():
                total += member.size
                if total > max_uncompressed:
                    raise BundleTooLargeError(
                        f"Uncompressed bundle exceeds cap of {max_uncompressed} bytes"
                    )
            try:
                # NOSONAR python:S930 -- 'filter' is the PEP 706 extraction
                # filter, valid since Python 3.12; SonarCloud's stubs lag.
                tar.extract(member, path=dest_dir, filter="data")
            except tarfile.FilterError as exc:
                raise BundleError(f"Unsafe tar member {member.name!r}: {exc}") from exc


def _read_manifest(dest_dir: Path) -> dict[str, Any]:
    manifest_path = dest_dir / MANIFEST_ARC
    if not manifest_path.is_file():
        raise BundleError(f"{MANIFEST_ARC} missing from bundle")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleError(f"{MANIFEST_ARC} is not valid JSON: {exc}") from exc


def _single_file(dest_dir: Path, subdir: str, label: str) -> Path:
    """Return the single regular file expected inside ``dest_dir/subdir``."""
    d = dest_dir / subdir
    if not d.is_dir():
        raise BundleError(f"Missing {label} directory: {subdir}/")
    files = [p for p in d.iterdir() if p.is_file()]
    if len(files) != 1:
        raise BundleError(
            f"Expected exactly one file under {subdir}/ ({label}); found {len(files)}"
        )
    return files[0]


# ---------------------------------------------------------------------------
# Taxprofiler — resolve + parse
# ---------------------------------------------------------------------------


@dataclass
class _TaxprofilerFiles:
    multiqc: Path
    pipeline_info: Path
    multiqc_html: Path | None
    # classifier name -> taxpasta TSV
    taxpasta: dict[str, Path] = field(default_factory=dict)
    # classifier name -> krona HTML (only present classifiers)
    krona: dict[str, Path] = field(default_factory=dict)
    metaval_dir: Path | None = None


def _check_optional_subtree(
    dest_dir: Path, subdir: str, present: bool, flag_name: str
) -> None:
    """Cross-check that a subdir is in the bundle iff its manifest flag is set."""
    exists = (dest_dir / subdir).is_dir()
    if present and not exists:
        raise BundleError(
            f"manifest {flag_name}=True but {subdir}/ missing from bundle"
        )
    if not present and exists:
        raise BundleError(f"{subdir}/ present but manifest {flag_name}=False")


def _resolve_taxprofiler_files(
    meta: TaxprofilerIngestMeta, dest_dir: Path
) -> _TaxprofilerFiles:
    """Locate every file the manifest claims, cross-check the tree against
    the manifest, and return the resolved Paths."""
    multiqc_file = dest_dir / MULTIQC_ARC
    if not multiqc_file.is_file():
        raise BundleError(f"{MULTIQC_ARC} missing from bundle")

    files = _TaxprofilerFiles(
        multiqc=multiqc_file,
        pipeline_info=_single_file(dest_dir, PIPELINE_INFO_DIR, "pipeline_info"),
        multiqc_html=None,
    )

    if meta.has_multiqc_report:
        files.multiqc_html = _single_file(
            dest_dir, MULTIQC_REPORT_DIR, "multiqc_report"
        )
    elif (dest_dir / MULTIQC_REPORT_DIR).is_dir():
        raise BundleError(
            "multiqc_report/ present but manifest has_multiqc_report=False"
        )

    krona_set = set(meta.classifiers_with_krona)
    for clf in meta.classifiers:
        files.taxpasta[clf.name] = _single_file(
            dest_dir,
            classifier_taxpasta_dir(clf.name),
            f"taxpasta for classifier {clf.name!r}",
        )
        if clf.name in krona_set:
            files.krona[clf.name] = _single_file(
                dest_dir,
                classifier_krona_dir(clf.name),
                f"krona for classifier {clf.name!r}",
            )
        elif (dest_dir / classifier_krona_dir(clf.name)).is_dir():
            raise BundleError(
                f"classifiers/{clf.name}/krona/ present but {clf.name!r} "
                "not in manifest.classifiers_with_krona"
            )

    # Cross-check: manifest must list every classifier subdir we see.
    classifier_root = dest_dir / CLASSIFIERS_DIR
    if classifier_root.is_dir():
        declared = {c.name for c in meta.classifiers}
        for sub in classifier_root.iterdir():
            if sub.is_dir() and sub.name not in declared:
                raise BundleError(
                    f"Bundle contains classifier {sub.name!r} not in manifest"
                )

    _check_optional_subtree(dest_dir, METAVAL_DIR, meta.has_metaval, "has_metaval")
    if meta.has_metaval:
        files.metaval_dir = dest_dir / METAVAL_DIR
    return files


async def _parse_taxprofiler_inputs(
    meta: TaxprofilerIngestMeta, files: _TaxprofilerFiles
) -> TaxprofilerIngestInputs:
    """Read and parse every file concurrently into typed TaxprofilerIngestInputs."""
    io_tasks: list = [
        asyncio.to_thread(read_pipeline_info, str(files.pipeline_info)),
        asyncio.to_thread(read_multiqc, str(files.multiqc)),
    ]
    classifier_order = [clf.name for clf in meta.classifiers]
    for name in classifier_order:
        io_tasks.append(asyncio.to_thread(load_taxpasta, str(files.taxpasta[name])))
    if files.multiqc_html is not None:
        io_tasks.append(asyncio.to_thread(_read_text_file, files.multiqc_html))
    krona_order = [name for name in classifier_order if name in files.krona]
    for name in krona_order:
        io_tasks.append(asyncio.to_thread(_read_text_file, files.krona[name]))
    if files.metaval_dir is not None:
        io_tasks.append(asyncio.to_thread(read_metaval, str(files.metaval_dir)))

    results = await asyncio.gather(*io_tasks)

    cursor = 0
    pipeline_info: PipelineInfoOutput = results[cursor]
    cursor += 1
    multiqc: MultiQCRaw = results[cursor]
    cursor += 1
    taxpasta: dict[str, pd.DataFrame] = {}
    for name in classifier_order:
        taxpasta[name] = results[cursor]
        cursor += 1
    multiqc_html: str | None = None
    if files.multiqc_html is not None:
        multiqc_html = results[cursor]
        cursor += 1
    krona_html: dict[str, str] = {}
    for name in krona_order:
        krona_html[name] = results[cursor]
        cursor += 1
    metaval = results[cursor] if files.metaval_dir is not None else None

    return TaxprofilerIngestInputs(
        multiqc=multiqc,
        pipeline_info=pipeline_info,
        taxpasta=taxpasta,
        krona_html=krona_html,
        multiqc_html=multiqc_html,
        metaval=metaval,
    )


async def load_taxprofiler_bundle(
    source: BinaryIO | Path, dest_dir: Path
) -> tuple[TaxprofilerIngestMeta, TaxprofilerIngestInputs]:
    """Extract ``source`` (a tar stream or path) into ``dest_dir`` and parse
    it into ``(meta, inputs)``.

    Raises ``BundleError`` on malformed bundles, ``BundleTooLargeError`` on
    oversized bundles, or ``pydantic.ValidationError`` on a manifest that
    doesn't match :class:`TaxprofilerIngestMeta`.
    """
    _safe_extract(source, dest_dir, settings.ingest_upload_max_uncompressed_bytes)
    meta = TaxprofilerIngestMeta.model_validate(_read_manifest(dest_dir))
    files = _resolve_taxprofiler_files(meta, dest_dir)
    inputs = await _parse_taxprofiler_inputs(meta, files)
    return meta, inputs


# ---------------------------------------------------------------------------
# Trana — resolve + parse
# ---------------------------------------------------------------------------


@dataclass
class _TranaSampleFiles:
    abundance: Path
    krona: Path | None = None
    nanoplot_unprocessed: Path | None = None
    nanoplot_processed: Path | None = None


@dataclass
class _TranaFiles:
    pipeline_info: Path
    multiqc_html: Path | None
    # sample_id -> per-sample files
    samples: dict[str, _TranaSampleFiles] = field(default_factory=dict)


def _resolve_trana_sample(sample, samples_root: Path) -> _TranaSampleFiles:
    """Locate the file set for a single Trana sample, validating that every
    file the manifest claims is actually present."""
    s_dir = samples_root / sample.sample_id
    if not s_dir.is_dir():
        raise BundleError(f"Missing samples/{sample.sample_id}/ in bundle")
    abundance = s_dir / "abundance.tsv"
    if not abundance.is_file():
        raise BundleError(f"Missing samples/{sample.sample_id}/abundance.tsv in bundle")
    files = _TranaSampleFiles(abundance=abundance)
    if sample.has_krona:
        krona = s_dir / "krona.html"
        if not krona.is_file():
            raise BundleError(
                f"manifest has_krona=True but samples/{sample.sample_id}/krona.html "
                "missing"
            )
        files.krona = krona
    if sample.has_nanoplot_unprocessed:
        np_unproc = s_dir / "nanoplot_unprocessed" / "NanoStats.txt"
        if not np_unproc.is_file():
            raise BundleError(
                f"manifest has_nanoplot_unprocessed=True but "
                f"samples/{sample.sample_id}/nanoplot_unprocessed/NanoStats.txt missing"
            )
        files.nanoplot_unprocessed = np_unproc
    if sample.has_nanoplot_processed:
        np_proc = s_dir / "nanoplot_processed" / "NanoStats.txt"
        if not np_proc.is_file():
            raise BundleError(
                f"manifest has_nanoplot_processed=True but "
                f"samples/{sample.sample_id}/nanoplot_processed/NanoStats.txt missing"
            )
        files.nanoplot_processed = np_proc
    return files


def _resolve_trana_files(meta: TranaIngestMeta, dest_dir: Path) -> _TranaFiles:
    files = _TranaFiles(
        pipeline_info=_single_file(dest_dir, PIPELINE_INFO_DIR, "pipeline_info"),
        multiqc_html=None,
    )
    if meta.has_multiqc_report:
        files.multiqc_html = _single_file(
            dest_dir, MULTIQC_REPORT_DIR, "multiqc_report"
        )
    elif (dest_dir / MULTIQC_REPORT_DIR).is_dir():
        raise BundleError(
            "multiqc_report/ present but manifest has_multiqc_report=False"
        )

    samples_root = dest_dir / SAMPLES_DIR
    if not samples_root.is_dir():
        raise BundleError(f"{SAMPLES_DIR}/ missing from bundle")

    declared_ids = {s.sample_id for s in meta.samples}
    for found in samples_root.iterdir():
        if not found.is_dir():
            raise BundleError(f"Unexpected file under {SAMPLES_DIR}/: {found.name}")
        if found.name not in declared_ids:
            raise BundleError(f"Bundle has unknown sample {found.name!r}")

    for s in meta.samples:
        files.samples[s.sample_id] = _resolve_trana_sample(s, samples_root)
    return files


def _trana_sample_tasks(
    sample_files: _TranaSampleFiles, io_tasks: list
) -> dict[str, int]:
    """Append the per-sample IO tasks to ``io_tasks`` and return a slot map
    of {result-name: index-into-results} for later assembly."""
    slot: dict[str, int] = {}
    slot["abundance"] = len(io_tasks)
    io_tasks.append(asyncio.to_thread(read_emu_abundance, str(sample_files.abundance)))
    if sample_files.nanoplot_unprocessed is not None:
        slot["nanoplot_unprocessed"] = len(io_tasks)
        io_tasks.append(
            asyncio.to_thread(read_nanostats, str(sample_files.nanoplot_unprocessed))
        )
    if sample_files.nanoplot_processed is not None:
        slot["nanoplot_processed"] = len(io_tasks)
        io_tasks.append(
            asyncio.to_thread(read_nanostats, str(sample_files.nanoplot_processed))
        )
    if sample_files.krona is not None:
        slot["krona"] = len(io_tasks)
        io_tasks.append(asyncio.to_thread(_read_text_file, sample_files.krona))
    return slot


async def _parse_trana_inputs(
    meta: TranaIngestMeta, files: _TranaFiles
) -> TranaIngestInputs:
    io_tasks: list = [
        asyncio.to_thread(read_pipeline_info, str(files.pipeline_info)),
    ]
    if files.multiqc_html is not None:
        io_tasks.append(asyncio.to_thread(_read_text_file, files.multiqc_html))

    per_sample_slices: dict[str, dict[str, int]] = {}
    sample_ids = [s.sample_id for s in meta.samples]
    for sid in sample_ids:
        per_sample_slices[sid] = _trana_sample_tasks(files.samples[sid], io_tasks)

    results = await asyncio.gather(*io_tasks)

    pipeline_info: PipelineInfoOutput = results[0]
    multiqc_html: str | None = results[1] if files.multiqc_html is not None else None

    def _at(slot: dict[str, int], key: str):
        idx = slot.get(key)
        return results[idx] if idx is not None else None

    sample_inputs: dict[str, TranaSampleInputs] = {}
    for sid in sample_ids:
        slot = per_sample_slices[sid]
        sample_inputs[sid] = TranaSampleInputs(
            taxon_entries=results[slot["abundance"]],
            nanoplot_unprocessed=_at(slot, "nanoplot_unprocessed"),
            nanoplot_processed=_at(slot, "nanoplot_processed"),
            krona_html=_at(slot, "krona"),
        )

    return TranaIngestInputs(
        pipeline_info=pipeline_info,
        samples=sample_inputs,
        multiqc_html=multiqc_html,
    )


async def load_trana_bundle(
    source: BinaryIO | Path, dest_dir: Path
) -> tuple[TranaIngestMeta, TranaIngestInputs]:
    _safe_extract(source, dest_dir, settings.ingest_upload_max_uncompressed_bytes)
    meta = TranaIngestMeta.model_validate(_read_manifest(dest_dir))
    files = _resolve_trana_files(meta, dest_dir)
    inputs = await _parse_trana_inputs(meta, files)
    return meta, inputs


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")
