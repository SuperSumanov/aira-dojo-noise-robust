"""Independent verifier for archived card-level generator provenance."""

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


class GeneratorProvenanceVerificationError(RuntimeError):
    """Raised when the archived provenance receipt cannot be reproduced."""


STRICT = (
    re.compile(rb"sk-[A-Za-z0-9._-]{12,}"),
    re.compile(rb"sk-or-v1-[A-Za-z0-9._-]{12,}"),
    re.compile(rb"(?i)bearer[ \t]+[A-Za-z0-9._-]{16,}"),
)
SAFE_MODEL = re.compile(r"^[A-Za-z0-9_./:+-]{1,160}$")


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def object_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise GeneratorProvenanceVerificationError(f"expected object: {path}")
    return value


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def registry_records(path: Path) -> dict[str, dict[str, Any]]:
    payload = object_json(path)
    if payload.get("schema_version") != "aira-dojo-corpus-batch-registry-v1":
        raise GeneratorProvenanceVerificationError("registry schema mismatch")
    records = payload.get("batches")
    if type(records) is not list:
        raise GeneratorProvenanceVerificationError("registry records missing")
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        if type(record) is not dict or set(record) != {"file", "sha256", "bytes", "rows"}:
            raise GeneratorProvenanceVerificationError("registry record malformed")
        name = record["file"]
        if type(name) is not str or Path(name).name != name or name in output:
            raise GeneratorProvenanceVerificationError("registry filename malformed")
        output[name] = record
    return output


def source_records(path: Path, registry: dict[str, dict[str, Any]]) -> list[tuple[str, Path]]:
    payload = object_json(path)
    if payload.get("schema_version") != "archived-generator-provenance-source-map-v1":
        raise GeneratorProvenanceVerificationError("source-map schema mismatch")
    records = payload.get("sources")
    if type(records) is not list:
        raise GeneratorProvenanceVerificationError("source-map records missing")
    output: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for record in records:
        if type(record) is not dict or set(record) != {"batch", "archive_dir"}:
            raise GeneratorProvenanceVerificationError("source-map record malformed")
        batch = record["batch"]
        root = Path(record["archive_dir"])
        if batch not in registry or batch in seen or not root.is_absolute() or not root.is_dir():
            raise GeneratorProvenanceVerificationError("source-map binding invalid")
        output.append((batch, root))
        seen.add(batch)
    return output


def release_ids(path: Path, expected: dict[str, Any]) -> set[str]:
    if path.stat().st_size != expected["bytes"] or file_sha(path) != expected["sha256"]:
        raise GeneratorProvenanceVerificationError("release batch lock mismatch")
    output: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if type(value) is not dict or not isinstance(value.get("id"), str):
                    raise GeneratorProvenanceVerificationError("release card id missing")
                output.add(value["id"])
    if len(output) != expected["rows"]:
        raise GeneratorProvenanceVerificationError("release card rows mismatch")
    return output


def member_map(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    output: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        normalized = posixpath.normpath(member.name)
        if member.name.startswith("/") or normalized == ".." or normalized.startswith("../"):
            raise GeneratorProvenanceVerificationError("unsafe archive path")
        if member.issym() or member.islnk():
            raise GeneratorProvenanceVerificationError("archive link rejected")
        if member.isfile():
            output[normalized] = member
    return output


def clean_member(archive: tarfile.TarFile, member: tarfile.TarInfo, limit: int) -> bytes:
    if member.size > limit:
        raise GeneratorProvenanceVerificationError("selected member oversized")
    stream = archive.extractfile(member)
    if stream is None:
        raise GeneratorProvenanceVerificationError("selected member unavailable")
    raw = stream.read(limit + 1)
    if len(raw) > limit or any(pattern.search(raw) for pattern in STRICT):
        raise GeneratorProvenanceVerificationError("selected member fails security gate")
    return raw


def direct_model(raw: bytes) -> str:
    config = json.loads(raw)
    try:
        operators = config["solver"]["operators"]
    except (TypeError, KeyError) as exc:
        raise GeneratorProvenanceVerificationError("operator model config missing") from exc
    if type(operators) is not dict or not operators:
        raise GeneratorProvenanceVerificationError("operator config malformed")
    models: set[str] = set()
    for operator in operators.values():
        try:
            model = operator["llm"]["client"]["model_id"]
        except (TypeError, KeyError) as exc:
            raise GeneratorProvenanceVerificationError("operator model id missing") from exc
        if not isinstance(model, str) or not SAFE_MODEL.fullmatch(model):
            raise GeneratorProvenanceVerificationError("operator model id unsafe")
        models.add(model)
    if len(models) != 1:
        raise GeneratorProvenanceVerificationError("operator models disagree")
    return next(iter(models))


def direct_journal_ids(raw: bytes) -> set[str]:
    decoded = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    competitions = {
        node.get("metric_info", {}).get("competition_id")
        for node in decoded
        if type(node) is dict and type(node.get("metric_info")) is dict
        and isinstance(node.get("metric_info", {}).get("competition_id"), str)
    }
    if len(competitions) != 1:
        return set()
    competition = next(iter(competitions))
    output: set[str] = set()
    for node in decoded:
        if type(node) is not dict or (node.get("code", "") == "" and node.get("step") == 0):
            continue
        node_id = node.get("id", node.get("step"))
        if node_id is not None:
            output.add(f"{competition}__{node_id}")
    return output


def recompute_batch(
    batch: str, root: Path, cards: Path, expected: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any], list[dict[str, Any]]]:
    targets = release_ids(cards, expected)
    candidates: dict[str, set[str]] = defaultdict(set)
    locks: list[dict[str, Any]] = []
    configs = paired = seen_ids = 0
    archives = sorted(path for path in root.iterdir() if path.is_file())
    for archive_path in archives:
        locks.append(
            {"batch": batch, "file": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": file_sha(archive_path)}
        )
        with tarfile.open(archive_path, "r:gz") as archive:
            members = member_map(archive)
            journals: dict[str, tarfile.TarInfo] = {}
            backup: dict[str, tarfile.TarInfo] = {}
            for name, member in members.items():
                base = posixpath.basename(name)
                if base in {"journal.jsonl", "JOURNAL.jsonl"}:
                    run_root = posixpath.dirname(posixpath.dirname(name))
                    (journals if base == "journal.jsonl" else backup)[run_root] = member
            for run_root, member in backup.items():
                journals.setdefault(run_root, member)
            for name, config_member in members.items():
                if posixpath.basename(name) != "dojo_config.json":
                    continue
                configs += 1
                config_root = posixpath.dirname(name)
                journal_member = journals.get(config_root)
                if journal_member is None:
                    roots = [root_name for root_name in journals if name.startswith(root_name + "/")]
                    if roots:
                        journal_member = journals[sorted(roots, key=len)[-1]]
                if journal_member is None:
                    continue
                model = direct_model(clean_member(archive, config_member, 5 * 1024 * 1024))
                ids = direct_journal_ids(clean_member(archive, journal_member, 512 * 1024 * 1024))
                paired += 1
                seen_ids += len(ids)
                for card_id in ids.intersection(targets):
                    candidates[card_id].add(model)
    exact: dict[str, str] = {}
    ambiguous = missing = 0
    for card_id in targets:
        models = candidates.get(card_id, set())
        if len(models) == 1:
            exact[card_id] = next(iter(models))
        elif models:
            ambiguous += 1
        else:
            missing += 1
    counts = Counter(exact.values())
    receipt = {
        "batch": batch,
        "target_rows": len(targets),
        "archives": len(archives),
        "configs": configs,
        "paired_runs": paired,
        "journal_card_ids_seen": seen_ids,
        "exact_rows": len(exact),
        "ambiguous_rows": ambiguous,
        "missing_rows": missing,
        "model_counts": dict(sorted(counts.items())),
    }
    return exact, receipt, locks


def load_overlay(path: Path) -> dict[tuple[str, str], str]:
    output: dict[tuple[str, str], str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if type(record) is not dict or set(record) != {
                "batch", "card_id", "generator_model_id", "evidence_status"
            }:
                raise GeneratorProvenanceVerificationError("overlay record malformed")
            if record["evidence_status"] != "exact_archived_dojo_config":
                raise GeneratorProvenanceVerificationError("overlay evidence status invalid")
            key = (record["batch"], record["card_id"])
            if key in output:
                raise GeneratorProvenanceVerificationError("duplicate overlay card")
            output[key] = record["generator_model_id"]
    return output


def verify(
    registry_path: Path,
    source_map_path: Path,
    cards_root: Path,
    overlay_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    registry = registry_records(registry_path)
    sources = source_records(source_map_path, registry)
    expected_overlay = load_overlay(overlay_path)
    actual_overlay: dict[tuple[str, str], str] = {}
    batch_receipts: list[dict[str, Any]] = []
    locks: list[dict[str, Any]] = []
    for batch, root in sources:
        exact, receipt, archive_locks = recompute_batch(
            batch, root, cards_root / batch, registry[batch]
        )
        actual_overlay.update({(batch, card_id): model for card_id, model in exact.items()})
        batch_receipts.append(receipt)
        locks.extend(archive_locks)
    if actual_overlay != expected_overlay:
        raise GeneratorProvenanceVerificationError("independent overlay mismatch")

    summary = object_json(summary_path)
    exact_rows = len(actual_overlay)
    target_rows = sum(item["target_rows"] for item in batch_receipts)
    ambiguous = sum(item["ambiguous_rows"] for item in batch_receipts)
    missing = sum(item["missing_rows"] for item in batch_receipts)
    model_counts = Counter(actual_overlay.values())
    expected_core = {
        "protocol": "archived-card-generator-provenance-v1",
        "status": "COMPLETE_EXACT" if not ambiguous and not missing else "PARTIAL",
        "coverage": {
            "batches": len(batch_receipts),
            "target_rows": target_rows,
            "exact_rows": exact_rows,
            "ambiguous_rows": ambiguous,
            "missing_rows": missing,
        },
        "model_counts": dict(sorted(model_counts.items())),
        "batches": batch_receipts,
        "overlay": {"file": overlay_path.name, "rows": exact_rows, "sha256": file_sha(overlay_path)},
        "batch_registry_sha256": file_sha(registry_path),
        "source_archive_lock_sha256": canonical_hash(locks),
    }
    if summary.get("protocol") != expected_core["protocol"] or summary.get("status") != expected_core["status"]:
        raise GeneratorProvenanceVerificationError("summary protocol/status mismatch")
    for key in ("coverage", "model_counts", "batches", "overlay"):
        if summary.get(key) != expected_core[key]:
            raise GeneratorProvenanceVerificationError(f"summary {key} mismatch")
    input_hashes = summary.get("input_sha256")
    if type(input_hashes) is not dict or input_hashes.get("batch_registry") != expected_core["batch_registry_sha256"]:
        raise GeneratorProvenanceVerificationError("summary registry hash mismatch")
    if input_hashes.get("source_archive_lock") != expected_core["source_archive_lock_sha256"]:
        raise GeneratorProvenanceVerificationError("summary archive lock mismatch")
    scope = summary.get("scope")
    if type(scope) is not dict or scope.get("prediction_or_prospective_resources_read") is not False:
        raise GeneratorProvenanceVerificationError("summary scope mismatch")
    return {
        "protocol": "archived-card-generator-provenance-independent-verifier-v1",
        "status": "PASS",
        "summary_sha256": file_sha(summary_path),
        "overlay_sha256": file_sha(overlay_path),
        "coverage": expected_core["coverage"],
        "model_counts": expected_core["model_counts"],
        "source_archive_lock_sha256": expected_core["source_archive_lock_sha256"],
        "service_provider_or_contract_entity_inferred": False,
        "release_cleared": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--cards-root", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(
        args.registry, args.source_map, args.cards_root, args.overlay, args.summary
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    coverage = receipt["coverage"]
    print(
        "ARCHIVED_GENERATOR_PROVENANCE_VERIFY=PASS "
        f"batches={coverage['batches']} target_rows={coverage['target_rows']} "
        f"exact_rows={coverage['exact_rows']} ambiguous_rows={coverage['ambiguous_rows']} "
        f"missing_rows={coverage['missing_rows']} release_cleared=false"
    )


if __name__ == "__main__":
    main()
