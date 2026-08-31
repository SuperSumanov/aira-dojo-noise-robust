#!/usr/bin/env python3
"""Outcome-blind longitudinal replication of archive-level disposition validity."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


PROTOCOL_NAME = "archive_disposition_longitudinal_replication_v1"
OBSERVATION_PROTOCOL = "prospective_archive_observer_v1"
HISTORICAL_LEDGER_PROTOCOL = "prospective_structural_rejection_ledger_v1"
HISTORICAL_LEDGER_STATUS = "OUTCOME_BLIND_ARCHIVE_DISPOSITION_AUDIT_COMPLETE"
SHA_RX = re.compile(r"[0-9a-f]{64}")
ENTRY_KEYS = {
    "baseline",
    "committed_archive_sha256",
    "committed_snapshot_sha256",
    "first_stable_at_epoch",
    "last_observed_at_epoch",
    "mtime_ns",
    "path",
    "present",
    "rejected_archive_sha256",
    "rejection_reason_code",
    "rejection_registry_sha256",
    "size",
    "stable_observations",
}


class ReplicationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReplicationError(f"{label} is absent, non-regular, or symlinked")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplicationError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise ReplicationError(f"{label} is not a JSON object")
    return value


def nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReplicationError(f"invalid {label}")
    return value


def unit_fraction(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReplicationError(f"invalid {label}")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ReplicationError(f"invalid {label}")
    return normalized


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value) is None:
        raise ReplicationError(f"invalid {label}")
    return value


def competition_from_relative(value: Any) -> str:
    if not isinstance(value, str):
        raise ReplicationError("archive identity is not a string")
    parts = PurePosixPath(value).parts
    if len(parts) != 2 or len(parts[0]) != 4 or not parts[0].isdigit():
        raise ReplicationError("archive identity is not a clean day/basename path")
    basename = parts[1]
    if not basename.endswith(".tar.gz"):
        raise ReplicationError("archive identity is not a tar.gz")
    stem = basename[: -len(".tar.gz")]
    seeded = re.fullmatch(r"(.+)-([0-9]+)seeds", stem)
    competition = seeded.group(1) if seeded is not None else stem
    if not competition or competition in {".", ".."}:
        raise ReplicationError("empty competition identity")
    return competition


def wilson_95(numerator: int, denominator: int) -> list[float]:
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise ReplicationError("invalid Wilson interval inputs")
    z = 1.959963984540054
    p = numerator / denominator
    z2 = z * z
    scale = 1.0 + z2 / denominator
    centre = (p + z2 / (2.0 * denominator)) / scale
    half = (
        z
        * math.sqrt((p * (1.0 - p) + z2 / (4.0 * denominator)) / denominator)
        / scale
    )
    return [centre - half, centre + half]


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator,
        "wilson_95": wilson_95(numerator, denominator),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("protocol") != PROTOCOL_NAME:
        raise ReplicationError("protocol identity mismatch")
    if protocol.get("frozen_before_current_mixed_disposition_readout") is not True:
        raise ReplicationError("protocol is not result-before frozen")
    access = protocol.get("access_contract")
    if access != {
        "observation_metadata_only": True,
        "archive_payloads_opened": False,
        "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
        "candidate_identities_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }:
        raise ReplicationError("access contract mismatch")


def historical_anchor(
    protocol: dict[str, Any], historical: dict[str, Any]
) -> tuple[dict[str, int], set[str], set[str]]:
    if (
        historical.get("protocol") != HISTORICAL_LEDGER_PROTOCOL
        or historical.get("status") != HISTORICAL_LEDGER_STATUS
    ):
        raise ReplicationError("historical ledger contract mismatch")
    counts = historical.get("counts")
    if not isinstance(counts, dict):
        raise ReplicationError("historical counts missing")
    expected = protocol.get("known_metadata_before_readout")
    if not isinstance(expected, dict):
        raise ReplicationError("known historical metadata missing")
    normalized = {
        "observed": nonnegative_int(counts.get("observed_archives"), "historical observed"),
        "baseline": nonnegative_int(counts.get("baseline_archives"), "historical baseline"),
        "accepted": nonnegative_int(
            counts.get("accepted_archive_transactions"), "historical accepted"
        ),
        "rejected": nonnegative_int(counts.get("rejected_archives"), "historical rejected"),
        "settled": nonnegative_int(
            counts.get("settled_archive_decisions"), "historical settled"
        ),
        "pending": nonnegative_int(counts.get("pending_archives"), "historical pending"),
        "rejected_competitions": nonnegative_int(
            counts.get("rejected_competitions"), "historical rejected competitions"
        ),
        "mixed_competitions": nonnegative_int(
            counts.get("mixed_disposition_competitions"), "historical mixed competitions"
        ),
    }
    if normalized != {
        "observed": nonnegative_int(
            expected.get("historical_observed_archives"), "expected historical observed"
        ),
        "baseline": 128,
        "accepted": 78,
        "rejected": 12,
        "settled": nonnegative_int(
            expected.get("historical_settled_postbaseline_archives"),
            "expected historical settled",
        ),
        "pending": 0,
        "rejected_competitions": nonnegative_int(
            expected.get("historical_rejected_competitions"),
            "expected historical rejected competitions",
        ),
        "mixed_competitions": nonnegative_int(
            expected.get("historical_mixed_disposition_competitions"),
            "expected historical mixed competitions",
        ),
    }:
        raise ReplicationError("historical committed counts do not reproduce")
    if normalized["observed"] != normalized["baseline"] + normalized["settled"]:
        raise ReplicationError("historical partition does not close")
    fractions = historical.get("fractions")
    if not isinstance(fractions, dict) or fractions.get(
        "mixed_disposition_over_rejected_competitions"
    ) != {
        "numerator": normalized["mixed_competitions"],
        "denominator": normalized["rejected_competitions"],
        "value": 1.0,
    }:
        raise ReplicationError("historical mixed-disposition anchor mismatch")
    accepted_competitions: set[str] = set()
    rejected_competitions: set[str] = set()
    timelines = historical.get("rejected_competition_timelines")
    if not isinstance(timelines, list):
        raise ReplicationError("historical competition timelines missing")
    for row in timelines:
        if not isinstance(row, dict) or not isinstance(row.get("competition"), str):
            raise ReplicationError("historical competition timeline malformed")
        competition = row["competition"]
        if competition in rejected_competitions:
            raise ReplicationError("duplicate historical competition timeline")
        rejected_count = nonnegative_int(
            row.get("rejected_archives"), "historical timeline rejected count"
        )
        accepted_count = nonnegative_int(
            row.get("accepted_archive_transactions"),
            "historical timeline accepted count",
        )
        if rejected_count == 0:
            raise ReplicationError("historical timeline lacks a rejection")
        rejected_competitions.add(competition)
        if accepted_count > 0:
            accepted_competitions.add(competition)
    if (
        len(rejected_competitions) != normalized["rejected_competitions"]
        or len(accepted_competitions & rejected_competitions)
        != normalized["mixed_competitions"]
    ):
        raise ReplicationError("historical competition sets do not reproduce")
    return normalized, accepted_competitions, rejected_competitions


def current_population(
    protocol: dict[str, Any], observations: dict[str, Any]
) -> dict[str, Any]:
    if set(observations) != {
        "baseline_sealed_at_epoch",
        "entries",
        "protocol",
        "source_root",
    } or observations.get("protocol") != OBSERVATION_PROTOCOL:
        raise ReplicationError("observations schema mismatch")
    entries = observations.get("entries")
    source_root = observations.get("source_root")
    if not isinstance(entries, dict) or not entries:
        raise ReplicationError("observation entries missing")
    if not isinstance(source_root, str) or not source_root.startswith("/"):
        raise ReplicationError("observation source root malformed")
    prefix = source_root.rstrip("/") + "/"
    known = protocol.get("known_metadata_before_readout")
    inputs = protocol.get("inputs")
    if not isinstance(known, dict) or not isinstance(inputs, dict):
        raise ReplicationError("protocol metadata missing")
    reasons_allowed = protocol.get("recognized_rejection_reasons")
    if not isinstance(reasons_allowed, list) or not reasons_allowed:
        raise ReplicationError("recognized rejection reasons missing")
    allowed = set(reasons_allowed)
    if len(allowed) != len(reasons_allowed) or not all(
        isinstance(item, str) and item for item in allowed
    ):
        raise ReplicationError("recognized rejection reasons malformed")

    counts = Counter()
    reasons: Counter[str] = Counter()
    accepted_competitions: set[str] = set()
    rejected_competitions: set[str] = set()
    postbaseline_hashes: set[str] = set()
    latest_seen = False
    latest = require_sha(inputs.get("current_latest_snapshot_sha256"), "current latest")
    for relative, row in entries.items():
        competition = competition_from_relative(relative)
        if not isinstance(row, dict) or set(row) != ENTRY_KEYS:
            raise ReplicationError("observation entry schema mismatch")
        if row.get("path") != prefix + relative or row.get("present") is not True:
            raise ReplicationError("observation path or presence mismatch")
        if nonnegative_int(row.get("stable_observations"), "stable observations") == 0:
            raise ReplicationError("archive lacks stable observations")
        nonnegative_int(row.get("size"), "archive size")
        nonnegative_int(row.get("mtime_ns"), "archive mtime")
        baseline = row.get("baseline")
        if not isinstance(baseline, bool):
            raise ReplicationError("baseline flag malformed")
        committed_archive = row.get("committed_archive_sha256")
        committed_snapshot = row.get("committed_snapshot_sha256")
        rejected_archive = row.get("rejected_archive_sha256")
        rejection_registry = row.get("rejection_registry_sha256")
        reason = row.get("rejection_reason_code")
        accepted = committed_archive is not None or committed_snapshot is not None
        rejected = rejected_archive is not None or rejection_registry is not None or reason is not None
        if sum((baseline, accepted, rejected)) > 1:
            raise ReplicationError("overlapping archive dispositions")
        if baseline:
            counts["baseline"] += 1
            continue
        if accepted:
            archive_sha = require_sha(committed_archive, "accepted archive hash")
            snapshot_sha = require_sha(committed_snapshot, "accepted snapshot hash")
            if archive_sha in postbaseline_hashes:
                raise ReplicationError("duplicate postbaseline archive payload hash")
            postbaseline_hashes.add(archive_sha)
            counts["accepted"] += 1
            accepted_competitions.add(competition)
            latest_seen |= snapshot_sha == latest
            continue
        if rejected:
            archive_sha = require_sha(rejected_archive, "rejected archive hash")
            require_sha(rejection_registry, "rejection registry hash")
            if not isinstance(reason, str) or reason not in allowed:
                raise ReplicationError("unknown rejection reason")
            if archive_sha in postbaseline_hashes:
                raise ReplicationError("duplicate postbaseline archive payload hash")
            postbaseline_hashes.add(archive_sha)
            counts["rejected"] += 1
            reasons[reason] += 1
            rejected_competitions.add(competition)
            continue
        counts["pending"] += 1

    normalized = {
        "observed": len(entries),
        "baseline": counts["baseline"],
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
        "pending": counts["pending"],
    }
    expected_counts = {
        "observed": nonnegative_int(
            inputs.get("current_source_archive_count"), "current source archive count"
        ),
        "baseline": nonnegative_int(
            known.get("current_baseline_archives"), "current baseline"
        ),
        "accepted": nonnegative_int(
            known.get("current_accepted_archives"), "current accepted"
        ),
        "rejected": nonnegative_int(
            known.get("current_rejected_archives"), "current rejected"
        ),
        "pending": nonnegative_int(
            known.get("current_pending_archives"), "current pending"
        ),
    }
    if normalized != expected_counts:
        raise ReplicationError("current source/observation partition mismatch")
    if normalized["pending"] != 0:
        raise ReplicationError("current population has pending archives")
    if normalized["observed"] != sum(normalized[key] for key in ("baseline", "accepted", "rejected", "pending")):
        raise ReplicationError("current partition does not close")
    if not latest_seen:
        raise ReplicationError("current latest snapshot is absent from accepted dispositions")
    return {
        "counts": normalized,
        "reason_counts": dict(sorted(reasons.items())),
        "accepted_competitions": accepted_competitions,
        "rejected_competitions": rejected_competitions,
        "postbaseline_unique_hashes": len(postbaseline_hashes),
    }


def build_result(
    protocol_path: Path,
    observations_path: Path,
    historical_ledger_path: Path,
) -> dict[str, Any]:
    protocol = read_object(protocol_path.resolve(), "protocol")
    validate_protocol(protocol)
    inputs = protocol.get("inputs")
    if not isinstance(inputs, dict):
        raise ReplicationError("protocol inputs missing")
    if sha256(observations_path.resolve()) != require_sha(
        inputs.get("current_observations_sha256"), "current observations hash"
    ):
        raise ReplicationError("current observations hash mismatch")
    if observations_path.stat().st_size != nonnegative_int(
        inputs.get("current_observations_bytes"), "current observations bytes"
    ):
        raise ReplicationError("current observations byte count mismatch")
    if sha256(historical_ledger_path.resolve()) != require_sha(
        inputs.get("historical_ledger_sha256"), "historical ledger hash"
    ):
        raise ReplicationError("historical ledger hash mismatch")
    observations = read_object(observations_path.resolve(), "observations")
    historical = read_object(historical_ledger_path.resolve(), "historical ledger")
    historical_counts, historical_accepted, historical_rejected = historical_anchor(
        protocol, historical
    )
    current = current_population(protocol, observations)
    current_counts = current["counts"]
    accepted_competitions = current["accepted_competitions"]
    rejected_competitions = current["rejected_competitions"]
    mixed = accepted_competitions & rejected_competitions
    rejected_competition_count = len(rejected_competitions)
    mixed_count = len(mixed)
    if rejected_competition_count == 0:
        raise ReplicationError("current population has no rejected competitions")
    extension = {
        "observed": current_counts["observed"] - historical_counts["observed"],
        "accepted": current_counts["accepted"] - historical_counts["accepted"],
        "rejected": current_counts["rejected"] - historical_counts["rejected"],
        "settled": (
            current_counts["accepted"]
            + current_counts["rejected"]
            - historical_counts["settled"]
        ),
    }
    if any(value < 0 for value in extension.values()):
        raise ReplicationError("current population is not an extension of historical counts")
    if extension["observed"] != extension["settled"]:
        raise ReplicationError("extension archive accounting mismatch")
    decision = protocol.get("decision_rule")
    if not isinstance(decision, dict):
        raise ReplicationError("decision rule missing")
    strong = decision.get("strong")
    partial = decision.get("partial")
    kill = decision.get("kill")
    if not all(isinstance(item, dict) for item in (strong, partial, kill)):
        raise ReplicationError("decision rule malformed")
    required_exact_fraction = unit_fraction(
        strong.get("required_current_mixed_disposition_fraction"),
        "strong exact mixed-disposition fraction",
    )
    partial_fraction = unit_fraction(
        partial.get("minimum_current_mixed_disposition_fraction"),
        "partial mixed-disposition fraction",
    )
    exact_mixed = mixed_count == rejected_competition_count
    if (
        rejected_competition_count
        >= nonnegative_int(strong.get("minimum_current_rejected_competitions"), "strong competition minimum")
        and extension["settled"]
        >= nonnegative_int(strong.get("minimum_extension_settled_archives"), "strong extension minimum")
        and exact_mixed
        and required_exact_fraction == 1.0
    ):
        status = strong.get("status")
    elif mixed_count / rejected_competition_count >= partial_fraction:
        status = partial.get("status")
    else:
        status = kill.get("status")
    if not isinstance(status, str) or not status:
        raise ReplicationError("decision status malformed")

    current_settled = current_counts["accepted"] + current_counts["rejected"]
    result = {
        "protocol": PROTOCOL_NAME,
        "status": status,
        "input_bindings": {
            "protocol_sha256": sha256(protocol_path.resolve()),
            "current_latest_snapshot_sha256": inputs["current_latest_snapshot_sha256"],
            "current_observations_sha256": inputs["current_observations_sha256"],
            "historical_ledger_sha256": inputs["historical_ledger_sha256"],
        },
        "integrity": {
            "source_count_equals_observation_count": True,
            "disposition_partition_mutually_exclusive_and_exhaustive": True,
            "pending_archives_zero": True,
            "postbaseline_archive_payload_hashes_unique": True,
            "all_rejection_reasons_recognized": True,
            "latest_snapshot_seen_in_accepted": True,
            "historical_anchor_reproduced": True,
        },
        "historical": {
            "observed_archives": historical_counts["observed"],
            "settled_postbaseline_archives": historical_counts["settled"],
            "accepted_archives": historical_counts["accepted"],
            "rejected_archives": historical_counts["rejected"],
            "rejected_competitions": len(historical_rejected),
            "mixed_disposition_competitions": len(
                historical_accepted & historical_rejected
            ),
            "rejection_rate": rate(
                historical_counts["rejected"], historical_counts["settled"]
            ),
        },
        "current": {
            "observed_archives": current_counts["observed"],
            "settled_postbaseline_archives": current_settled,
            "baseline_archives": current_counts["baseline"],
            "accepted_archives": current_counts["accepted"],
            "rejected_archives": current_counts["rejected"],
            "pending_archives": current_counts["pending"],
            "postbaseline_unique_archive_hashes": current[
                "postbaseline_unique_hashes"
            ],
            "rejected_competitions": rejected_competition_count,
            "mixed_disposition_competitions": mixed_count,
            "nonmixed_rejected_competitions": rejected_competition_count - mixed_count,
            "mixed_disposition_fraction": rate(mixed_count, rejected_competition_count),
            "rejection_rate": rate(current_counts["rejected"], current_settled),
            "rejection_reason_counts": current["reason_counts"],
        },
        "extension_beyond_historical_anchor": {
            "observed_archives": extension["observed"],
            "settled_archives": extension["settled"],
            "accepted_archives": extension["accepted"],
            "rejected_archives": extension["rejected"],
            "rejection_rate": rate(extension["rejected"], extension["settled"]),
        },
        "decision": {
            "strong_gate_passed": status == strong.get("status"),
            "partial_gate_passed": status == partial.get("status"),
            "kill_gate_triggered": status == kill.get("status"),
            "identities_emitted": False,
        },
        "access_attestation": {
            "observation_metadata_only": True,
            "archive_payloads_opened": False,
            "labels_grades_outcomes_predictions_accuracy_or_utility_read": False,
            "candidate_identities_emitted": False,
            "randomness_used": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
        "claim_boundary": {
            "supports_archive_level_fail_closed_validation": status
            == strong.get("status"),
            "supports_task_whitelist_or_blacklist": False,
            "estimates_metadata_repair_causal_effect": False,
            "estimates_predictor_accuracy_scaling_or_search_utility": False,
            "claims_rejection_rate_stationarity": False,
        },
    }
    return result


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ReplicationError("output already exists")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ReplicationError("output parent is absent or unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--historical-ledger", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_result(
            args.protocol, args.observations, args.historical_ledger
        )
        write_new(args.output.resolve(), result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "current_rejected_competitions": result["current"][
                        "rejected_competitions"
                    ],
                    "current_mixed_disposition_competitions": result["current"][
                        "mixed_disposition_competitions"
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (OSError, ReplicationError, TypeError, ZeroDivisionError) as exc:
        print(f"ARCHIVE_DISPOSITION_REPLICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
