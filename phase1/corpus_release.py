"""Byte-exact corpus releases built from immutable Git LFS batch files.

The batch registry is append-only.  A release selects a prefix of that registry and
pins the canonical hash of the selected records, the historical transformation
protocol, and the exact output row/byte/SHA-256 triple.  Consequently, adding a new
batch cannot change an old release and changing an old batch fails before rebuilding.

Usage:
    python -m phase1.corpus_release verify-inputs --release phase1/corpus_releases/v11.json
    python -m phase1.corpus_release build --release phase1/corpus_releases/v11.json \
        --output /tmp/cards_current_v11.jsonl --receipt /tmp/cards_current_v11.receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import sys
import tempfile
from typing import Any, Iterable


REGISTRY_SCHEMA = "aira-dojo-corpus-batch-registry-v1"
RELEASE_SCHEMA = "aira-dojo-corpus-release-v1"
PROTOCOL_BASIC = "legacy-run-id-v6-basic"
PROTOCOL_SANITIZED_V10 = "legacy-run-id-v6-sanitized-v10"
PROTOCOL_SANITIZED_V11 = "legacy-run-id-v6-sanitized-v11"
# Compatibility name for callers/tests that construct a synthetic v10-style release.
PROTOCOL_SANITIZED = PROTOCOL_SANITIZED_V10
PROTOCOLS = {PROTOCOL_BASIC, PROTOCOL_SANITIZED_V10, PROTOCOL_SANITIZED_V11}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
VERSION = re.compile(r"v[0-9]+\Z")
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"

# Frozen from phase1/build_cards.py at the v10/v11 release commits.  Keeping this
# mapping here prevents a future task taxonomy edit from silently changing old bytes.
TASK_TYPE_V10 = {
    "spaceship-titanic": "tabular",
    "playground-series-s3e18": "tabular",
    "nomad2018-predict-transparent-conductors": "tabular",
    "tabular-playground-series-may-2022": "tabular",
    "tabular-playground-series-dec-2021": "tabular",
    "aerial-cactus-identification": "image-cls",
    "aptos2019-blindness-detection": "image-cls",
    "dog-breed-identification": "image-cls",
    "histopathologic-cancer-detection": "image-cls",
    "leaf-classification": "image-cls",
    "denoising-dirty-documents": "image-cls",
    "ranzcr-clip-catheter-line-classification": "image-cls",
    "chaii-hindi-and-tamil-question-answering": "nlp",
    "spooky-author-identification": "nlp",
    "random-acts-of-pizza": "nlp",
    "google-quest-challenge": "nlp",
    "text-normalization-challenge-english-language": "nlp",
    "text-normalization-challenge-russian-language": "nlp",
    "tweet-sentiment-extraction": "nlp",
    "learning-agency-lab-automated-essay-scoring-2": "nlp",
    "us-patent-phrase-to-phrase-matching": "nlp",
    "kuzushiji-recognition": "image-cls",
    "petfinder-pawpularity-score": "image-cls",
    "whale-categorization-playground": "image-cls",
    "mlsp-2013-birds": "image-cls",
}
TASK_TYPE_V11 = {**TASK_TYPE_V10, "dogs-vs-cats-redux-kernels-edition": "image-cls"}


class CorpusReleaseError(RuntimeError):
    """A release contract or payload failed closed."""


def _exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    actual = set(value)
    if actual != expected:
        raise CorpusReleaseError(
            f"{where} keys differ: missing={sorted(expected - actual)} "
            f"unknown={sorted(actual - expected)}"
        )


def _read_json(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusReleaseError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusReleaseError(f"expected JSON object in {path}")
    return value, raw


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_batch_lock(records: Iterable[dict[str, Any]]) -> str:
    """Hash the ordered selected registry records with an unambiguous encoding."""

    raw = json.dumps(
        list(records), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return _sha256_bytes(raw)


def _validate_batch_record(record: Any, index: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise CorpusReleaseError(f"registry batch {index} is not an object")
    _exact_keys(record, {"file", "sha256", "bytes", "rows"}, f"registry batch {index}")
    name = record["file"]
    if (
        not isinstance(name, str)
        or pathlib.PurePath(name).name != name
        or not name.startswith("cards_")
        or not name.endswith(".jsonl")
    ):
        raise CorpusReleaseError(f"unsafe batch filename at index {index}: {name!r}")
    if not isinstance(record["sha256"], str) or not HEX64.fullmatch(record["sha256"]):
        raise CorpusReleaseError(f"invalid sha256 for registry batch {index}")
    if not isinstance(record["bytes"], int) or isinstance(record["bytes"], bool) or record["bytes"] <= 0:
        raise CorpusReleaseError(f"invalid byte count for registry batch {index}")
    if not isinstance(record["rows"], int) or isinstance(record["rows"], bool) or record["rows"] <= 0:
        raise CorpusReleaseError(f"invalid row count for registry batch {index}")
    return record


def load_contracts(
    release_path: pathlib.Path, registry_path: pathlib.Path | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    """Load strict release/registry contracts and resolve the pinned batch prefix."""

    release_path = release_path.resolve()
    registry_path = (
        registry_path.resolve()
        if registry_path is not None
        else release_path.with_name("batch_registry.json")
    )
    release, release_raw = _read_json(release_path)
    registry, registry_raw = _read_json(registry_path)
    _exact_keys(
        release,
        {
            "schema_version",
            "version",
            "release_commit",
            "rebuild_protocol",
            "batch_count",
            "batch_lock_sha256",
            "output",
        },
        "release",
    )
    _exact_keys(registry, {"schema_version", "batches"}, "registry")
    if release["schema_version"] != RELEASE_SCHEMA:
        raise CorpusReleaseError("unsupported release schema")
    if registry["schema_version"] != REGISTRY_SCHEMA:
        raise CorpusReleaseError("unsupported registry schema")
    if not isinstance(release["version"], str) or not VERSION.fullmatch(release["version"]):
        raise CorpusReleaseError("invalid release version")
    if not isinstance(release["release_commit"], str) or not HEX40.fullmatch(release["release_commit"]):
        raise CorpusReleaseError("invalid release_commit")
    if release["rebuild_protocol"] not in PROTOCOLS:
        raise CorpusReleaseError("unsupported rebuild_protocol")
    output = release["output"]
    if not isinstance(output, dict):
        raise CorpusReleaseError("release output is not an object")
    _exact_keys(output, {"file", "rows", "bytes", "sha256"}, "release output")
    expected_name = f"cards_current_{release['version']}.jsonl"
    if output["file"] != expected_name:
        raise CorpusReleaseError(f"release output filename must be {expected_name}")
    if not isinstance(output["rows"], int) or isinstance(output["rows"], bool) or output["rows"] <= 0:
        raise CorpusReleaseError("invalid release output rows")
    if not isinstance(output["bytes"], int) or isinstance(output["bytes"], bool) or output["bytes"] <= 0:
        raise CorpusReleaseError("invalid release output bytes")
    if not isinstance(output["sha256"], str) or not HEX64.fullmatch(output["sha256"]):
        raise CorpusReleaseError("invalid release output sha256")
    batches_raw = registry["batches"]
    if not isinstance(batches_raw, list):
        raise CorpusReleaseError("registry batches is not a list")
    batches = [_validate_batch_record(record, i) for i, record in enumerate(batches_raw)]
    names = [record["file"] for record in batches]
    if len(set(names)) != len(names):
        raise CorpusReleaseError("duplicate batch filename in registry")
    count = release["batch_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0 or count > len(batches):
        raise CorpusReleaseError("invalid release batch_count")
    selected = batches[:count]
    actual_lock = canonical_batch_lock(selected)
    if release["batch_lock_sha256"] != actual_lock:
        raise CorpusReleaseError(
            f"batch lock mismatch: expected={release['batch_lock_sha256']} actual={actual_lock}"
        )
    hashes = {
        "release_descriptor_sha256": _sha256_bytes(release_raw),
        "batch_registry_sha256": _sha256_bytes(registry_raw),
        "selected_batch_lock_sha256": actual_lock,
    }
    return release, selected, hashes


def _file_stats(path: pathlib.Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    rows = 0
    first = b""
    with path.open("rb") as handle:
        for line in handle:
            if rows == 0:
                first = line
            digest.update(line)
            size += len(line)
            rows += 1
    if first == LFS_POINTER_PREFIX:
        raise CorpusReleaseError(
            f"{path} is an unsmudged Git LFS pointer; run git lfs pull against the fork remote"
        )
    return {"sha256": digest.hexdigest(), "bytes": size, "rows": rows}


def verify_batch_payloads(
    phase1_dir: pathlib.Path, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    verified = []
    for record in records:
        path = phase1_dir / record["file"]
        if not path.is_file():
            raise CorpusReleaseError(f"missing immutable batch: {path}")
        actual = _file_stats(path)
        expected = {key: record[key] for key in ("sha256", "bytes", "rows")}
        if actual != expected:
            raise CorpusReleaseError(
                f"immutable batch mismatch for {record['file']}: expected={expected} actual={actual}"
            )
        verified.append({"file": record["file"], **actual})
    return verified


def reconstruct_run_map(
    phase1_dir: pathlib.Path, records: list[dict[str, Any]]
) -> tuple[dict[str, str], dict[str, int]]:
    """Reproduce the legacy per-file contiguous segmentation, with stricter audits."""

    run_of: dict[str, str] = {}
    parent_of: dict[str, Any] = {}
    segment_tasks: dict[str, set[str]] = {}
    parsed_rows = 0
    for record in records:
        name = record["file"]
        previous_task: str | None = None
        previous_step: Any = None
        segment = -1
        with (phase1_dir / name).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    row = json.loads(line)
                    card_id = row["id"]
                    task = row["task"]["name"]
                    lineage = row["lineage"]
                    step = lineage.get("step") or 0
                    parent = lineage.get("parent_id")
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise CorpusReleaseError(
                        f"invalid card schema in {name}:{line_number}: {exc}"
                    ) from exc
                if not isinstance(card_id, str) or not card_id:
                    raise CorpusReleaseError(f"invalid card id in {name}:{line_number}")
                if card_id in run_of:
                    raise CorpusReleaseError(f"duplicate card id across release: {card_id}")
                if task != previous_task or (
                    previous_step is not None and step <= previous_step
                ):
                    segment += 1
                run_id = f"{name}:{segment}"
                run_of[card_id] = run_id
                parent_of[card_id] = parent
                segment_tasks.setdefault(run_id, set()).add(task)
                previous_task, previous_step = task, step
                parsed_rows += 1
    mixed_task_segments = sum(len(tasks) > 1 for tasks in segment_tasks.values())
    cross_segment_parents = sum(
        bool(parent and parent in run_of and run_of[parent] != run_of[card_id])
        for card_id, parent in parent_of.items()
    )
    if mixed_task_segments or cross_segment_parents:
        raise CorpusReleaseError(
            "legacy run reconstruction rejected: "
            f"mixed_task_segments={mixed_task_segments} "
            f"cross_segment_parents={cross_segment_parents}"
        )
    return run_of, {
        "cards": parsed_rows,
        "runs": len(segment_tasks),
        "mixed_task_segments": mixed_task_segments,
        "cross_segment_parents": cross_segment_parents,
    }


def _transform_basic(row: dict[str, Any], run_id: str) -> bytes:
    row["run_id"] = run_id
    row.setdefault("provenance", {})["run_id_source"] = "reconstructed:file-contiguity"
    return (json.dumps(row) + "\n").encode("utf-8")


def _transform_sanitized(
    row: dict[str, Any], run_id: str, task_types: dict[str, str]
) -> bytes:
    task_name = row["task"]["name"]
    if task_name not in task_types:
        raise CorpusReleaseError(f"unknown task in frozen taxonomy: {task_name}")
    row["task"]["type"] = task_types[task_name]
    label = row.get("label") or {}
    label_values = [label.get("graded"), label.get("y_norm")]
    if any(
        value is not None
        and (not isinstance(value, (int, float)) or not math.isfinite(float(value)))
        for value in label_values
    ):
        label["graded"] = None
        label["y_norm"] = None
        label["medal_bucket"] = "invalid"
        row["label"] = label
        row.setdefault("provenance", {})["label_status"] = "quarantined:nonfinite_label"
    row["run_id"] = run_id
    row.setdefault("provenance", {})["run_id_source"] = "reconstructed:file-contiguity"
    row["provenance"]["task_type_source"] = "phase1.build_cards:TASK_TYPE"
    return (json.dumps(row, allow_nan=False) + "\n").encode("utf-8")


def _atomic_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = pathlib.Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def build_release(
    release_path: pathlib.Path,
    output_path: pathlib.Path,
    registry_path: pathlib.Path | None = None,
    phase1_dir: pathlib.Path | None = None,
    receipt_path: pathlib.Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    release_path = release_path.resolve()
    release, records, contract_hashes = load_contracts(release_path, registry_path)
    phase1_dir = (
        phase1_dir.resolve()
        if phase1_dir is not None
        else release_path.parent.parent.resolve()
    )
    output_path = output_path.resolve()
    if output_path.exists() and not overwrite:
        raise CorpusReleaseError(f"output already exists (use --overwrite): {output_path}")
    if receipt_path is not None and receipt_path.resolve().exists() and not overwrite:
        raise CorpusReleaseError(f"receipt already exists (use --overwrite): {receipt_path}")
    verified_batches = verify_batch_payloads(phase1_dir, records)
    run_map, segmentation = reconstruct_run_map(phase1_dir, records)
    expected = release["output"]
    if segmentation["cards"] != expected["rows"]:
        raise CorpusReleaseError(
            f"segmentation row count mismatch: {segmentation['cards']} != {expected['rows']}"
        )
    if release["rebuild_protocol"] == PROTOCOL_BASIC:
        transform = _transform_basic
    else:
        task_types = (
            TASK_TYPE_V10
            if release["rebuild_protocol"] == PROTOCOL_SANITIZED_V10
            else TASK_TYPE_V11
        )

        def transform(row: dict[str, Any], run_id: str) -> bytes:
            return _transform_sanitized(row, run_id, task_types)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    temp = pathlib.Path(temp_name)
    digest = hashlib.sha256()
    output_rows = 0
    output_bytes = 0
    try:
        with os.fdopen(fd, "wb") as output:
            for record in records:
                name = record["file"]
                with (phase1_dir / name).open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, 1):
                        try:
                            row = json.loads(line)
                            card_id = row["id"]
                            encoded = transform(row, run_map[card_id])
                        except (json.JSONDecodeError, KeyError, TypeError) as exc:
                            raise CorpusReleaseError(
                                f"cannot transform {name}:{line_number}: {exc}"
                            ) from exc
                        output.write(encoded)
                        digest.update(encoded)
                        output_rows += 1
                        output_bytes += len(encoded)
            output.flush()
            os.fsync(output.fileno())
        actual = {
            "file": expected["file"],
            "rows": output_rows,
            "bytes": output_bytes,
            "sha256": digest.hexdigest(),
        }
        if actual != expected:
            raise CorpusReleaseError(
                f"rebuilt output mismatch for {release['version']}: "
                f"expected={expected} actual={actual}"
            )
        os.replace(temp, output_path)
    finally:
        if temp.exists():
            temp.unlink()
    receipt = {
        "status": "VERIFIED_BYTE_EXACT_CORPUS_REBUILD",
        "schema_version": RELEASE_SCHEMA,
        "version": release["version"],
        "release_commit": release["release_commit"],
        "rebuild_protocol": release["rebuild_protocol"],
        "batch_count": len(records),
        "verified_batch_rows": sum(record["rows"] for record in verified_batches),
        "output": {**expected, "path": str(output_path)},
        "segmentation": segmentation,
        "contract_hashes": contract_hashes,
        "software": {"python": platform.python_version(), "platform": platform.platform()},
    }
    if receipt_path is not None:
        _atomic_json(receipt_path.resolve(), receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("verify-inputs", "build"):
        child = subparsers.add_parser(command)
        child.add_argument("--release", type=pathlib.Path, required=True)
        child.add_argument("--registry", type=pathlib.Path)
        child.add_argument("--phase1-dir", type=pathlib.Path)
        if command == "build":
            child.add_argument("--output", type=pathlib.Path, required=True)
            child.add_argument("--receipt", type=pathlib.Path)
            child.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify-inputs":
            release_path = args.release.resolve()
            release, records, hashes = load_contracts(release_path, args.registry)
            phase1_dir = (
                args.phase1_dir.resolve()
                if args.phase1_dir is not None
                else release_path.parent.parent.resolve()
            )
            verified = verify_batch_payloads(phase1_dir, records)
            result = {
                "status": "VERIFIED_IMMUTABLE_CORPUS_BATCHES",
                "version": release["version"],
                "batch_count": len(verified),
                "batch_rows": sum(record["rows"] for record in verified),
                "contract_hashes": hashes,
            }
        else:
            result = build_release(
                release_path=args.release,
                output_path=args.output,
                registry_path=args.registry,
                phase1_dir=args.phase1_dir,
                receipt_path=args.receipt,
                overwrite=args.overwrite,
            )
    except (CorpusReleaseError, OSError) as exc:
        print(f"CORPUS_RELEASE_REJECTED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
