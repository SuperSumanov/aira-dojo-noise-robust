"""Reconstruct card-level generator model provenance from historical archives.

The five late historical batches were previously provider/model-unmapped at the
batch level.  Their source archives contain a credential-free ``dojo_config``
beside each run journal.  This tool binds those model IDs to release card IDs
without extracting archives or reading ``env_variables.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


class GeneratorProvenanceError(RuntimeError):
    """Raised when archived provenance cannot be reconstructed safely."""


MAX_CONFIG_BYTES = 5 * 1024 * 1024
MAX_JOURNAL_BYTES = 512 * 1024 * 1024
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_./:+-]{1,160}$")
CARD_ID_PREFIX = re.compile(rb'^\{"id":\s*("(?:[^"\\]|\\.)*")')
STRICT_CREDENTIAL_SHAPES = (
    re.compile(rb"sk-[A-Za-z0-9._-]{12,}"),
    re.compile(rb"sk-or-v1-[A-Za-z0-9._-]{12,}"),
    re.compile(rb"(?i)bearer[ \t]+[A-Za-z0-9._-]{16,}"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeneratorProvenanceError(f"cannot read JSON object: {path}") from exc
    if type(value) is not dict:
        raise GeneratorProvenanceError(f"expected JSON object: {path}")
    return value


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_object(path)
    if payload.get("schema_version") != "aira-dojo-corpus-batch-registry-v1":
        raise GeneratorProvenanceError("unexpected batch registry schema")
    records = payload.get("batches")
    if type(records) is not list or not records:
        raise GeneratorProvenanceError("batch registry must be non-empty")
    output: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != {"file", "sha256", "bytes", "rows"}:
            raise GeneratorProvenanceError(f"invalid registry record {index}")
        name = record["file"]
        if type(name) is not str or Path(name).name != name or name in output:
            raise GeneratorProvenanceError(f"unsafe or duplicate registry file at {index}")
        if type(record["rows"]) is not int or record["rows"] <= 0:
            raise GeneratorProvenanceError(f"invalid registry rows at {index}")
        if type(record["bytes"]) is not int or record["bytes"] <= 0:
            raise GeneratorProvenanceError(f"invalid registry bytes at {index}")
        if type(record["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
            raise GeneratorProvenanceError(f"invalid registry hash at {index}")
        output[name] = record
    return output


def load_source_map(path: Path, registry: dict[str, dict[str, Any]]) -> list[tuple[str, Path]]:
    payload = read_object(path)
    if payload.get("schema_version") != "archived-generator-provenance-source-map-v1":
        raise GeneratorProvenanceError("unexpected source-map schema")
    records = payload.get("sources")
    if type(records) is not list or not records:
        raise GeneratorProvenanceError("source map must be non-empty")
    output: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != {"batch", "archive_dir"}:
            raise GeneratorProvenanceError(f"invalid source-map record {index}")
        batch = record["batch"]
        archive_dir = record["archive_dir"]
        if type(batch) is not str or batch not in registry or batch in seen:
            raise GeneratorProvenanceError(f"unknown or duplicate source batch at {index}")
        if type(archive_dir) is not str:
            raise GeneratorProvenanceError(f"invalid archive directory at {index}")
        root = Path(archive_dir)
        if not root.is_absolute() or not root.is_dir():
            raise GeneratorProvenanceError(f"archive directory unavailable at {index}")
        output.append((batch, root))
        seen.add(batch)
    return output


def safe_members(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    selected: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        normalized = posixpath.normpath(member.name)
        if member.name.startswith("/") or normalized == ".." or normalized.startswith("../"):
            raise GeneratorProvenanceError("unsafe archive path")
        if member.issym() or member.islnk():
            raise GeneratorProvenanceError("archive link rejected")
        if member.isfile():
            selected[normalized] = member  # accepted ingest semantics: last duplicate wins
    return selected


def read_selected_member(
    archive: tarfile.TarFile, member: tarfile.TarInfo, limit: int
) -> bytes:
    if member.size > limit:
        raise GeneratorProvenanceError("oversized selected archive member")
    stream = archive.extractfile(member)
    if stream is None:
        raise GeneratorProvenanceError("missing selected archive member stream")
    raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise GeneratorProvenanceError("oversized selected archive member stream")
    if any(pattern.search(raw) for pattern in STRICT_CREDENTIAL_SHAPES):
        raise GeneratorProvenanceError("credential shape in selected config or journal")
    return raw


def collect_model_ids(value: object, output: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"model_id", "model_name", "model"} and isinstance(child, str):
                candidate = child.strip()
                if (
                    SAFE_IDENTIFIER.fullmatch(candidate)
                    and "://" not in candidate
                    and not candidate.startswith(("/", "."))
                ):
                    output.add(candidate)
            collect_model_ids(child, output)
    elif isinstance(value, list):
        for child in value:
            collect_model_ids(child, output)


def model_from_config(raw: bytes) -> str:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeneratorProvenanceError("invalid dojo config JSON") from exc
    model_ids: set[str] = set()
    collect_model_ids(value, model_ids)
    if len(model_ids) != 1:
        raise GeneratorProvenanceError("dojo config does not identify exactly one model")
    return next(iter(model_ids))


def card_ids_from_journal(raw: bytes) -> set[str]:
    nodes: list[dict[str, Any]] = []
    competition_id: str | None = None
    try:
        for raw_line in raw.splitlines():
            if not raw_line.strip():
                continue
            node = json.loads(raw_line)
            if type(node) is not dict:
                continue
            nodes.append(node)
            metric_info = node.get("metric_info")
            if type(metric_info) is dict and isinstance(metric_info.get("competition_id"), str):
                competition_id = metric_info["competition_id"]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeneratorProvenanceError("invalid journal JSONL") from exc
    if not competition_id:
        return set()
    output: set[str] = set()
    for node in nodes:
        if node.get("code", "") == "" and node.get("step") == 0:
            continue
        node_id = node.get("id", node.get("step"))
        if node_id is not None:
            output.add(f"{competition_id}__{node_id}")
    return output


def load_release_card_ids(path: Path, expected: dict[str, Any]) -> set[str]:
    if not path.is_file():
        raise GeneratorProvenanceError(f"release batch unavailable: {path.name}")
    if path.stat().st_size != expected["bytes"] or sha256(path) != expected["sha256"]:
        raise GeneratorProvenanceError(f"release batch lock mismatch: {path.name}")
    output: set[str] = set()
    rows = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            rows += 1
            match = CARD_ID_PREFIX.match(raw_line)
            if match is None:
                raise GeneratorProvenanceError(f"card id is not the first JSON field: {path.name}")
            card_id = json.loads(match.group(1))
            if not isinstance(card_id, str) or not card_id or card_id in output:
                raise GeneratorProvenanceError(f"invalid or duplicate card id: {path.name}")
            output.add(card_id)
    if rows != expected["rows"] or rows != len(output):
        raise GeneratorProvenanceError(f"release batch row mismatch: {path.name}")
    return output


def pair_journals(members: dict[str, tarfile.TarInfo]) -> dict[str, tarfile.TarInfo]:
    primary: dict[str, tarfile.TarInfo] = {}
    fallback: dict[str, tarfile.TarInfo] = {}
    for path, member in members.items():
        basename = posixpath.basename(path)
        if basename not in {"journal.jsonl", "JOURNAL.jsonl"}:
            continue
        run_root = posixpath.dirname(posixpath.dirname(path))
        (primary if basename == "journal.jsonl" else fallback)[run_root] = member
    for run_root, member in fallback.items():
        primary.setdefault(run_root, member)
    return primary


def reconstruct_batch(
    batch: str,
    cards_path: Path,
    expected: dict[str, Any],
    archive_root: Path,
) -> tuple[list[dict[str, str]], dict[str, Any], list[dict[str, Any]]]:
    targets = load_release_card_ids(cards_path, expected)
    candidates: dict[str, set[str]] = defaultdict(set)
    archives = sorted(path for path in archive_root.iterdir() if path.is_file())
    if not archives:
        raise GeneratorProvenanceError(f"no source archives for {batch}")
    archive_locks: list[dict[str, Any]] = []
    configs = paired_runs = journal_card_ids_seen = 0
    for archive_path in archives:
        archive_locks.append(
            {"batch": batch, "file": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": sha256(archive_path)}
        )
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                members = safe_members(archive)
                journals = pair_journals(members)
                for config_path, config_member in members.items():
                    if posixpath.basename(config_path) != "dojo_config.json":
                        continue
                    configs += 1
                    config_root = posixpath.dirname(config_path)
                    journal_member = journals.get(config_root)
                    if journal_member is None:
                        roots = [
                            root
                            for root in journals
                            if config_path.startswith(root.rstrip("/") + "/")
                        ]
                        if roots:
                            journal_member = journals[max(roots, key=len)]
                    if journal_member is None:
                        continue
                    model = model_from_config(
                        read_selected_member(archive, config_member, MAX_CONFIG_BYTES)
                    )
                    card_ids = card_ids_from_journal(
                        read_selected_member(archive, journal_member, MAX_JOURNAL_BYTES)
                    )
                    paired_runs += 1
                    journal_card_ids_seen += len(card_ids)
                    for card_id in card_ids & targets:
                        candidates[card_id].add(model)
        except (OSError, tarfile.TarError) as exc:
            raise GeneratorProvenanceError(f"cannot inspect source archive for {batch}") from exc

    overlay: list[dict[str, str]] = []
    ambiguous = missing = 0
    model_counts: Counter[str] = Counter()
    for card_id in sorted(targets):
        models = candidates.get(card_id, set())
        if len(models) == 1:
            model = next(iter(models))
            model_counts[model] += 1
            overlay.append(
                {
                    "batch": batch,
                    "card_id": card_id,
                    "generator_model_id": model,
                    "evidence_status": "exact_archived_dojo_config",
                }
            )
        elif len(models) > 1:
            ambiguous += 1
        else:
            missing += 1
    summary = {
        "batch": batch,
        "target_rows": len(targets),
        "archives": len(archives),
        "configs": configs,
        "paired_runs": paired_runs,
        "journal_card_ids_seen": journal_card_ids_seen,
        "exact_rows": len(overlay),
        "ambiguous_rows": ambiguous,
        "missing_rows": missing,
        "model_counts": dict(sorted(model_counts.items())),
    }
    return overlay, summary, archive_locks


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(
    registry_path: Path,
    source_map_path: Path,
    cards_root: Path,
    overlay_path: Path,
    summary_path: Path,
    require_complete: bool,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    sources = load_source_map(source_map_path, registry)
    overlay: list[dict[str, str]] = []
    batch_summaries: list[dict[str, Any]] = []
    archive_locks: list[dict[str, Any]] = []
    for batch, archive_root in sources:
        rows, batch_summary, locks = reconstruct_batch(
            batch, cards_root / batch, registry[batch], archive_root
        )
        overlay.extend(rows)
        batch_summaries.append(batch_summary)
        archive_locks.extend(locks)

    exact = len(overlay)
    total = sum(item["target_rows"] for item in batch_summaries)
    ambiguous = sum(item["ambiguous_rows"] for item in batch_summaries)
    missing = sum(item["missing_rows"] for item in batch_summaries)
    if exact + ambiguous + missing != total:
        raise GeneratorProvenanceError("coverage accounting mismatch")
    if require_complete and (ambiguous or missing):
        raise GeneratorProvenanceError("complete provenance required but unresolved rows remain")

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    with overlay_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in overlay:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    model_counts = Counter(record["generator_model_id"] for record in overlay)
    summary = {
        "protocol": "archived-card-generator-provenance-v1",
        "status": "COMPLETE_EXACT" if not ambiguous and not missing else "PARTIAL",
        "input_sha256": {
            "batch_registry": sha256(registry_path),
            "source_archive_lock": canonical_hash(archive_locks),
        },
        "scope": {
            "historical_release_only": True,
            "card_payload_fields_retained": ["id"],
            "label_values_retained": False,
            "prediction_or_prospective_resources_read": False,
            "env_variables_read": False,
            "service_provider_or_contract_entity_inferred": False,
            "release_cleared": False,
            "counts_as_distinct_claim_evidence": False,
        },
        "coverage": {
            "batches": len(batch_summaries),
            "target_rows": total,
            "exact_rows": exact,
            "ambiguous_rows": ambiguous,
            "missing_rows": missing,
        },
        "model_counts": dict(sorted(model_counts.items())),
        "batches": batch_summaries,
        "overlay": {"file": overlay_path.name, "rows": exact, "sha256": sha256(overlay_path)},
    }
    write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--cards-root", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    payload = build(
        args.registry,
        args.source_map,
        args.cards_root,
        args.overlay,
        args.summary,
        args.require_complete,
    )
    coverage = payload["coverage"]
    print(
        "ARCHIVED_GENERATOR_PROVENANCE=PASS "
        f"batches={coverage['batches']} target_rows={coverage['target_rows']} "
        f"exact_rows={coverage['exact_rows']} ambiguous_rows={coverage['ambiguous_rows']} "
        f"missing_rows={coverage['missing_rows']} release_cleared=false"
    )


if __name__ == "__main__":
    main()
