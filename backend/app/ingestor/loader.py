# app/ingestor/loader.py
"""Loader layer for the ingest pipeline.

The CLI uploads a tar.gz bundle to the server. The loader is the only place
that touches the filesystem on the server side: it safely extracts the bundle
into a TemporaryDirectory, parses every referenced file into typed content
via the existing reader modules, and returns ``(meta, inputs)`` ready for the
orchestrator. The orchestrator never sees user-supplied paths.

Bundle layout (taxprofiler)::

    manifest.json                                  # IngestMeta as JSON
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
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

from app.config import settings
from app.ingestor.emu_reader import read_emu_abundance
from app.ingestor.metaval_reader import read_metaval
from app.ingestor.multiqc_reader import read_multiqc
from app.ingestor.models import (
    IngestInputs,
    MultiQCRaw,
    PipelineInfoOutput,
    TranaIngestInputs,
    TranaSampleInputs,
)
from app.ingestor.nanoplot_reader import read_nanostats
from app.ingestor.pipeline_info_reader import read_pipeline_info
from app.ingestor.taxpasta_reader import load_taxpasta
from app.models.sample import IngestMeta, TranaIngestMeta


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


def _safe_extract(
    source: BinaryIO | Path, dest_dir: Path, max_uncompressed: int
) -> None:
    """Extract a tar stream into ``dest_dir`` with all the usual safeguards.

    ``source`` is either a file-like object (preferred — streamed extraction,
    no seek required) or a Path (still supported for tests).

    - Refuses absolute member names, symlinks, hardlinks, device nodes.
    - Refuses paths that escape ``dest_dir`` (``..`` traversal).
    - Enforces ``max_uncompressed`` as a running sum of member sizes.

    Uses tarfile's streaming mode (``r|*``) when given a fileobj: the tar is
    read sequentially, members are extracted to disk in one pass, no
    intermediate write of the whole bundle. Compression is auto-detected
    (gzip / bzip2 / xz / none).
    """
    total = 0
    dest_resolved = dest_dir.resolve()

    if isinstance(source, Path):
        tar = tarfile.open(source, mode="r:*")
    else:
        tar = tarfile.open(fileobj=source, mode="r|*")

    with tar:
        for member in tar:
            if member.islnk() or member.issym():
                raise BundleError(f"Refusing symlink/hardlink in bundle: {member.name}")
            if member.isdev():
                raise BundleError(f"Refusing device node in bundle: {member.name}")
            if member.name.startswith("/") or ".." in Path(member.name).parts:
                raise BundleError(f"Unsafe member name: {member.name}")
            target = (dest_resolved / member.name).resolve()
            try:
                target.relative_to(dest_resolved)
            except ValueError as exc:
                raise BundleError(f"Member escapes destination: {member.name}") from exc

            if member.isreg():
                total += member.size
                if total > max_uncompressed:
                    raise BundleTooLargeError(
                        f"Uncompressed bundle exceeds cap of {max_uncompressed} bytes"
                    )

            # `data` filter (Py 3.12+) re-applies the same protections at
            # extract-time as a defence in depth.
            tar.extract(member, path=dest_dir, filter="data")


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


def _optional_single_file(dest_dir: Path, subdir: str, label: str) -> Path | None:
    d = dest_dir / subdir
    if not d.is_dir():
        return None
    files = [p for p in d.iterdir() if p.is_file()]
    if len(files) != 1:
        raise BundleError(
            f"Expected exactly one file under {subdir}/ ({label}); found {len(files)}"
        )
    return files[0]


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


async def load_taxprofiler_bundle(
    source: BinaryIO | Path, dest_dir: Path
) -> tuple[IngestMeta, IngestInputs]:
    """Extract ``source`` (a tar stream or path) into ``dest_dir`` and parse
    it into ``(meta, inputs)``.

    Raises ``BundleError`` on malformed bundles, ``BundleTooLargeError`` on
    oversized bundles, or ``pydantic.ValidationError`` on a manifest that
    doesn't match :class:`IngestMeta`.
    """
    _safe_extract(source, dest_dir, settings.ingest_upload_max_uncompressed_bytes)
    meta = IngestMeta.model_validate(_read_manifest(dest_dir))

    # Resolve required + optional files from the extracted tree.
    multiqc_file = dest_dir / MULTIQC_ARC
    if not multiqc_file.is_file():
        raise BundleError(f"{MULTIQC_ARC} missing from bundle")

    pipeline_info_file = _single_file(dest_dir, PIPELINE_INFO_DIR, "pipeline_info")

    multiqc_html_file: Path | None = None
    if meta.has_multiqc_report:
        multiqc_html_file = _single_file(dest_dir, MULTIQC_REPORT_DIR, "multiqc_report")
    else:
        if (dest_dir / MULTIQC_REPORT_DIR).is_dir():
            raise BundleError(
                "multiqc_report/ present but manifest has_multiqc_report=False"
            )

    taxpasta_files: dict[str, Path] = {}
    krona_files: dict[str, Path] = {}
    krona_set = set(meta.classifiers_with_krona)
    for clf in meta.classifiers:
        taxpasta_files[clf.name] = _single_file(
            dest_dir,
            classifier_taxpasta_dir(clf.name),
            f"taxpasta for classifier {clf.name!r}",
        )
        if clf.name in krona_set:
            krona_files[clf.name] = _single_file(
                dest_dir,
                classifier_krona_dir(clf.name),
                f"krona for classifier {clf.name!r}",
            )
        else:
            if (dest_dir / classifier_krona_dir(clf.name)).is_dir():
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

    metaval_dir = dest_dir / METAVAL_DIR
    if meta.has_metaval and not metaval_dir.is_dir():
        raise BundleError("manifest has_metaval=True but metaval/ missing from bundle")
    if not meta.has_metaval and metaval_dir.exists():
        raise BundleError("metaval/ present but manifest has_metaval=False")

    # Fan out blocking file reads concurrently.
    io_tasks: list = [
        asyncio.to_thread(read_pipeline_info, str(pipeline_info_file)),
        asyncio.to_thread(read_multiqc, str(multiqc_file)),
    ]
    classifier_order = [clf.name for clf in meta.classifiers]
    for name in classifier_order:
        io_tasks.append(asyncio.to_thread(load_taxpasta, str(taxpasta_files[name])))
    if multiqc_html_file is not None:
        io_tasks.append(asyncio.to_thread(_read_text_file, multiqc_html_file))
    krona_order = [name for name in classifier_order if name in krona_files]
    for name in krona_order:
        io_tasks.append(asyncio.to_thread(_read_text_file, krona_files[name]))
    if meta.has_metaval:
        io_tasks.append(asyncio.to_thread(read_metaval, str(metaval_dir)))

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
    if multiqc_html_file is not None:
        multiqc_html = results[cursor]
        cursor += 1
    krona_html: dict[str, str] = {}
    for name in krona_order:
        krona_html[name] = results[cursor]
        cursor += 1
    metaval = results[cursor] if meta.has_metaval else None

    inputs = IngestInputs(
        multiqc=multiqc,
        pipeline_info=pipeline_info,
        taxpasta=taxpasta,
        krona_html=krona_html,
        multiqc_html=multiqc_html,
        metaval=metaval,
    )
    return meta, inputs


async def load_trana_bundle(
    source: BinaryIO | Path, dest_dir: Path
) -> tuple[TranaIngestMeta, TranaIngestInputs]:
    _safe_extract(source, dest_dir, settings.ingest_upload_max_uncompressed_bytes)
    meta = TranaIngestMeta.model_validate(_read_manifest(dest_dir))

    pipeline_info_file = _single_file(dest_dir, PIPELINE_INFO_DIR, "pipeline_info")

    multiqc_html_file: Path | None = None
    if meta.has_multiqc_report:
        multiqc_html_file = _single_file(dest_dir, MULTIQC_REPORT_DIR, "multiqc_report")
    elif (dest_dir / MULTIQC_REPORT_DIR).is_dir():
        raise BundleError(
            "multiqc_report/ present but manifest has_multiqc_report=False"
        )

    # Resolve per-sample files
    sample_files: dict[str, dict[str, Path]] = {}
    declared_ids = {s.sample_id for s in meta.samples}
    samples_root = dest_dir / SAMPLES_DIR
    if not samples_root.is_dir():
        raise BundleError(f"{SAMPLES_DIR}/ missing from bundle")

    for found in samples_root.iterdir():
        if not found.is_dir():
            raise BundleError(f"Unexpected file under {SAMPLES_DIR}/: {found.name}")
        if found.name not in declared_ids:
            raise BundleError(f"Bundle has unknown sample {found.name!r}")

    for s in meta.samples:
        s_dir = samples_root / s.sample_id
        if not s_dir.is_dir():
            raise BundleError(f"Missing samples/{s.sample_id}/ in bundle")
        abundance = s_dir / "abundance.tsv"
        if not abundance.is_file():
            raise BundleError(f"Missing samples/{s.sample_id}/abundance.tsv in bundle")
        files: dict[str, Path] = {"abundance": abundance}
        if s.has_krona:
            krona = s_dir / "krona.html"
            if not krona.is_file():
                raise BundleError(
                    f"manifest has_krona=True but samples/{s.sample_id}/krona.html missing"
                )
            files["krona"] = krona
        if s.has_nanoplot_unprocessed:
            np_unproc = s_dir / "nanoplot_unprocessed" / "NanoStats.txt"
            if not np_unproc.is_file():
                raise BundleError(
                    f"manifest has_nanoplot_unprocessed=True but "
                    f"samples/{s.sample_id}/nanoplot_unprocessed/NanoStats.txt missing"
                )
            files["nanoplot_unprocessed"] = np_unproc
        if s.has_nanoplot_processed:
            np_proc = s_dir / "nanoplot_processed" / "NanoStats.txt"
            if not np_proc.is_file():
                raise BundleError(
                    f"manifest has_nanoplot_processed=True but "
                    f"samples/{s.sample_id}/nanoplot_processed/NanoStats.txt missing"
                )
            files["nanoplot_processed"] = np_proc
        sample_files[s.sample_id] = files

    # Fan out concurrently
    sample_ids = [s.sample_id for s in meta.samples]
    io_tasks: list = [
        asyncio.to_thread(read_pipeline_info, str(pipeline_info_file)),
    ]
    if multiqc_html_file is not None:
        io_tasks.append(asyncio.to_thread(_read_text_file, multiqc_html_file))

    # Flatten per-sample tasks into a single gather. Track the slice indices.
    per_sample_slices: dict[str, dict[str, int]] = {}
    for sid in sample_ids:
        files = sample_files[sid]
        slot: dict[str, int] = {}
        slot["abundance"] = len(io_tasks)
        io_tasks.append(asyncio.to_thread(read_emu_abundance, str(files["abundance"])))
        if "nanoplot_unprocessed" in files:
            slot["nanoplot_unprocessed"] = len(io_tasks)
            io_tasks.append(
                asyncio.to_thread(read_nanostats, str(files["nanoplot_unprocessed"]))
            )
        if "nanoplot_processed" in files:
            slot["nanoplot_processed"] = len(io_tasks)
            io_tasks.append(
                asyncio.to_thread(read_nanostats, str(files["nanoplot_processed"]))
            )
        if "krona" in files:
            slot["krona"] = len(io_tasks)
            io_tasks.append(asyncio.to_thread(_read_text_file, files["krona"]))
        per_sample_slices[sid] = slot

    results = await asyncio.gather(*io_tasks)

    pipeline_info: PipelineInfoOutput = results[0]
    multiqc_html: str | None = results[1] if multiqc_html_file is not None else None

    sample_inputs: dict[str, TranaSampleInputs] = {}
    for sid in sample_ids:
        slot = per_sample_slices[sid]
        sample_inputs[sid] = TranaSampleInputs(
            taxon_entries=results[slot["abundance"]],
            nanoplot_unprocessed=(
                results[slot["nanoplot_unprocessed"]]
                if "nanoplot_unprocessed" in slot
                else None
            ),
            nanoplot_processed=(
                results[slot["nanoplot_processed"]]
                if "nanoplot_processed" in slot
                else None
            ),
            krona_html=results[slot["krona"]] if "krona" in slot else None,
        )

    inputs = TranaIngestInputs(
        pipeline_info=pipeline_info,
        samples=sample_inputs,
        multiqc_html=multiqc_html,
    )
    return meta, inputs


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")
