#!/usr/bin/env python3
"""Independent reconstruction of source-choice materialization and label separation."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from phase1 import source_decision_answerability as upstream


PROTOCOL = "source-choice-benchmark-materialization-v2"
GROUP_SCHEMA = "source-choice-group-v2"
LABEL_SCHEMA = "source-choice-label-vault-v2"
ROLES = ("train", "frozen", "extension")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SECRET = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
CONSTRUCTION_HEADER = (
    "role", "parent", "task", "run_id", "source_size", "eligible", "exclusion_reasons",
)


class VerificationError(RuntimeError):
    pass


def digest_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def digest_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def identity_hash(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def reject_secret_bytes(blob: bytes, where: str) -> None:
    if SECRET.search(blob):
        raise VerificationError(f"credential shape found: {where}")


def reject_secret_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value = overlap + chunk
            if SECRET.search(value):
                raise VerificationError(f"credential shape found: {path.name}")
            overlap = value[-256:]


def text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"invalid text: {where}")
    return value


def integer(value: Any, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise VerificationError(f"invalid integer: {where}")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"invalid integer: {where}") from exc
    if str(result) != str(value).strip() or result < minimum:
        raise VerificationError(f"integer outside contract: {where}")
    return result


def boolean(value: Any, where: str) -> bool:
    if value in (True, "True"):
        return True
    if value in (False, "False"):
        return False
    raise VerificationError(f"invalid boolean: {where}")


def object_json(path: Path, where: str) -> dict[str, Any]:
    reject_secret_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON: {where}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"JSON object required: {where}")
    return value


def protocol_json(path: Path) -> dict[str, Any]:
    value = object_json(path, "protocol")
    if value.get("protocol") != PROTOCOL or value.get("allow_result_rescue") is not False:
        raise VerificationError("protocol identity/rescue mismatch")
    inputs = value.get("inputs")
    expected = value.get("expected")
    if not isinstance(inputs, dict) or any(
        not isinstance(item, str) or not HEX64.fullmatch(item) for item in inputs.values()
    ):
        raise VerificationError("protocol input hashes invalid")
    if not isinstance(expected, dict):
        raise VerificationError("protocol expected block absent")
    if value.get("candidate_order") != "ascending_sha256_of_raw_candidate_id":
        raise VerificationError("candidate order mismatch")
    if value.get("choice_context") != "task_run_parent_hash_plus_candidate_code_only":
        raise VerificationError("choice context mismatch")
    if value.get("parent_code_included") is not False or value.get("parent_card_required") is not False:
        raise VerificationError("parent context was reintroduced")
    if value.get("frozen_label_policy") != "separate_opaque_read_only_vault":
        raise VerificationError("vault policy mismatch")
    return value


def parse_roots(values: Sequence[str], protocol: dict[str, Any]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise VerificationError("root argument lacks alias")
        alias, raw = item.split("=", 1)
        path = Path(raw).resolve()
        if alias in roots or not path.is_dir():
            raise VerificationError("duplicate or missing root")
        roots[alias] = path
    if sorted(roots) != sorted(protocol.get("journal_root_aliases") or []):
        raise VerificationError("root aliases differ from protocol")
    return roots


def verify_hash(path: Path, expected: str, name: str) -> None:
    if not path.is_file() or digest_file(path) != expected:
        raise VerificationError(f"input hash mismatch: {name}")
    reject_secret_file(path)


def read_construction(path: Path, protocol: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    counts = collections.Counter()
    eligible_counts = collections.Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CONSTRUCTION_HEADER:
            raise VerificationError("construction header mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = text(raw.get("role"), f"construction {line_number}:role")
            parent = text(raw.get("parent"), f"construction {line_number}:parent")
            if role not in ROLES or (role, parent) in rows:
                raise VerificationError("construction identity invalid")
            eligible = boolean(raw.get("eligible"), f"construction {line_number}:eligible")
            if eligible and str(raw.get("exclusion_reasons") or ""):
                raise VerificationError("eligible construction row has exclusion")
            rows[(role, parent)] = {
                "task": text(raw.get("task"), f"construction {line_number}:task"),
                "run_id": text(raw.get("run_id"), f"construction {line_number}:run"),
                "source_size": integer(raw.get("source_size"), f"construction {line_number}:size", 2),
                "eligible": eligible,
            }
            counts[role] += 1
            eligible_counts[role] += int(eligible)
    expected = protocol["expected"]
    if len(rows) != expected["construction_rows"]:
        raise VerificationError("construction total mismatch")
    if {role: counts[role] for role in ROLES} != expected["construction_rows_by_role"]:
        raise VerificationError("construction role totals mismatch")
    if {role: eligible_counts[role] for role in ROLES} != expected[
        "eligible_construction_rows_by_role"
    ]:
        raise VerificationError("construction eligible totals mismatch")
    return rows


def read_status(path: Path, protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"status JSON invalid: {line_number}") from exc
            if not isinstance(raw, dict):
                raise VerificationError("status row not object")
            child = text(raw.get("child_id"), f"status {line_number}:child")
            if child in rows:
                raise VerificationError("duplicate status child")
            rows[child] = raw
    if len(rows) != protocol["expected"]["status_registry_rows"]:
        raise VerificationError("status row total mismatch")
    return rows


def read_cards(path: Path, protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"card JSON invalid: {line_number}") from exc
            if not isinstance(raw, dict):
                raise VerificationError("card row not object")
            card_id = text(raw.get("id"), f"card {line_number}:id")
            if card_id in cards:
                raise VerificationError("duplicate card id")
            cards[card_id] = raw
    if len(cards) != protocol["expected"]["cards"]:
        raise VerificationError("card total mismatch")
    return cards


def journal_paths(root: Path) -> list[Path]:
    chosen: dict[Path, Path] = {}
    for candidate in root.rglob("*"):
        if not candidate.is_file() or candidate.name.lower() != "journal.jsonl":
            continue
        run = candidate.parent.parent
        previous = chosen.get(run)
        if previous is None or (
            "checkpoint" in candidate.parts and "checkpoint" not in previous.parts
        ):
            chosen[run] = candidate
    return [chosen[key] for key in sorted(chosen, key=lambda value: value.as_posix())]


def recover_journal_candidates(
    roots: dict[str, Path], targets: dict[str, dict[str, dict[str, str]]]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    needed = set(targets)
    blobs: dict[str, bytes] = {}
    counts: dict[str, int] = {}
    scanned = secret_skips = 0
    for alias, root in sorted(roots.items()):
        paths = journal_paths(root)
        counts[alias] = len(paths)
        for path in paths:
            blob = path.read_bytes()
            scanned += 1
            sha = digest_bytes(blob)
            if SECRET.search(blob):
                secret_skips += 1
                if sha in needed:
                    raise VerificationError("needed journal has credential shape")
                continue
            if sha in needed:
                if sha in blobs and blobs[sha] != blob:
                    raise VerificationError("needed journal SHA collision")
                blobs[sha] = blob
    if set(blobs) != needed:
        raise VerificationError("needed journal set not found")
    recovered: dict[str, dict[str, Any]] = {}
    for sha in sorted(blobs):
        blob = blobs[sha]
        reject_secret_bytes(blob, sha)
        try:
            lines = blob.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise VerificationError("needed journal not UTF-8") from exc
        nodes: list[dict[str, Any]] = []
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                node = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"needed journal JSON invalid: {number}") from exc
            if not isinstance(node, dict):
                raise VerificationError("needed journal row not object")
            nodes.append(node)
        tasks = {
            str(metric["competition_id"])
            for node in nodes
            if isinstance((metric := node.get("metric_info")), dict) and metric.get("competition_id")
        }
        if len(tasks) != 1:
            raise VerificationError("needed journal task ambiguous")
        task = next(iter(tasks))
        by_step: dict[Any, dict[str, Any]] = {}
        for node in nodes:
            if node.get("step") in by_step:
                raise VerificationError("duplicate journal step")
            by_step[node.get("step")] = node
        seen: set[str] = set()
        for node in nodes:
            raw_id = node.get("id", node.get("step"))
            child = f"{task}__{raw_id}"
            if child not in targets[sha]:
                continue
            if child in seen:
                raise VerificationError("duplicate target node")
            seen.add(child)
            expected = targets[sha][child]
            parents = node.get("parents") or []
            if not isinstance(parents, list) or len(parents) != 1 or parents[0] not in by_step:
                raise VerificationError("target parent linkage absent")
            parent_node = by_step[parents[0]]
            parent_raw = parent_node.get("id", parent_node.get("step"))
            if task != expected["task"] or f"{task}__{parent_raw}" != expected["parent"]:
                raise VerificationError("target journal context mismatch")
            code = node.get("code")
            if not isinstance(code, str) or not code:
                raise VerificationError("target journal code absent")
            operators = node.get("operators_used") or []
            operator = operators[0] if isinstance(operators, list) and operators else "Draft"
            step = integer(node.get("step"), "journal step")
            raw_depth = node.get("depth")
            depth = integer(raw_depth if raw_depth is not None else len(parents), "journal depth")
            recovered[child] = {
                "candidate_id_sha256": identity_hash(child),
                "code": code,
                "code_sha256": digest_bytes(code.encode("utf-8")),
                "operator": str(operator),
                "step": step,
                "depth": depth,
                "provenance": "journal_recovered",
                "source_journal_sha256": sha,
            }
        if seen != set(targets[sha]):
            raise VerificationError("journal target closure mismatch")
    return recovered, {
        "canonical_journals_by_root": dict(sorted(counts.items())),
        "journal_files_scanned": scanned,
        "credential_shape_journals_skipped": secret_skips,
        "needed_journal_shas": len(needed),
        "needed_journal_shas_found": len(blobs),
    }


def card_parts(card: dict[str, Any], card_id: str) -> tuple[str, str, dict[str, Any]]:
    task_value = card.get("task")
    task = text(task_value.get("name") if isinstance(task_value, dict) else None, "card task")
    run = text(card.get("run_id"), "card run")
    lineage = card.get("lineage")
    if not isinstance(lineage, dict):
        raise VerificationError(f"card lineage absent: {identity_hash(card_id)}")
    return task, run, lineage


def expected_card_candidate(
    cards: dict[str, dict[str, Any]], child: str, task: str, run: str, parent: str
) -> dict[str, Any]:
    card = cards.get(child)
    if card is None:
        raise VerificationError("expected card candidate missing")
    card_task, card_run, lineage = card_parts(card, child)
    if card_task != task or card_run != run or lineage.get("parent_id") != parent:
        raise VerificationError("card candidate context mismatch")
    code = card.get("code")
    operator = lineage.get("op")
    if not isinstance(code, str) or not code or not isinstance(operator, str) or not operator:
        raise VerificationError("card candidate code/operator absent")
    return {
        "candidate_id_sha256": identity_hash(child),
        "code": code,
        "code_sha256": digest_bytes(code.encode("utf-8")),
        "operator": operator,
        "step": integer(lineage.get("step"), "card candidate step"),
        "depth": integer(lineage.get("depth", lineage.get("tree_depth")), "card candidate depth"),
        "provenance": "card",
        "source_journal_sha256": None,
    }


def read_jsonl(path: Path, where: str) -> list[dict[str, Any]]:
    reject_secret_file(path)
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"invalid output JSONL: {where}:{number}") from exc
            if not isinstance(row, dict):
                raise VerificationError(f"output row not object: {where}:{number}")
            if canonical(row) + b"\n" != line.encode("utf-8"):
                raise VerificationError(f"output JSONL not canonical: {where}:{number}")
            rows.append(row)
    return rows


def verify(arguments: argparse.Namespace) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.source_commit):
        raise VerificationError("source commit invalid")
    protocol_path = Path(arguments.protocol).resolve()
    protocol = protocol_json(protocol_path)
    paths = {
        "cards": Path(arguments.cards).resolve(),
        "answerability_module": Path(upstream.__file__).resolve(),
        "answerability_protocol": Path(arguments.answerability_protocol).resolve(),
        "per_parent": Path(arguments.per_parent).resolve(),
        "identity_registry": Path(arguments.identity_registry).resolve(),
        "status_edges": Path(arguments.status_edges).resolve(),
        "status_registry": Path(arguments.status_registry).resolve(),
        "construction": Path(arguments.construction).resolve(),
        "answerability_summary": Path(arguments.answerability_summary).resolve(),
        "support_summary": Path(arguments.support_summary).resolve(),
    }
    for name, path in paths.items():
        verify_hash(path, protocol["inputs"][f"{name}_sha256"], name)
    roots = parse_roots(arguments.root, protocol)
    public = Path(arguments.public_output).resolve()
    vault = Path(arguments.vault_output).resolve()
    if not public.is_dir() or not vault.is_dir():
        raise VerificationError("public/vault output missing")

    upstream_protocol = upstream.load_protocol(paths["answerability_protocol"])
    parents = upstream.load_parents(paths["per_parent"], upstream_protocol)
    identities = upstream.load_identity(paths["identity_registry"], upstream_protocol, parents)
    pair_paths = upstream.parse_pair_arguments(arguments.pair)
    pairs = upstream.load_pairs(pair_paths, upstream_protocol, parents)
    status_edges = upstream.load_status_edges(
        paths["status_edges"], upstream_protocol, parents, identities, pairs
    )
    answer_rows = upstream.build_parent_rows(parents, identities, pairs, status_edges)
    parent_by_hash: dict[tuple[str, str], str] = {}
    for role, parent in parents:
        key = (role, identity_hash(parent))
        if key in parent_by_hash:
            raise VerificationError("parent identity hash collision")
        parent_by_hash[key] = parent
    construction = read_construction(paths["construction"], protocol)
    status = read_status(paths["status_registry"], protocol)
    cards = read_cards(paths["cards"], protocol)

    selected: list[dict[str, Any]] = []
    for row in answer_rows:
        if row["status_winner"] is None:
            continue
        parent = parent_by_hash.get((row["role"], row["parent_sha256"]))
        if parent is None:
            raise VerificationError("answer parent hash lacks raw identity")
        incomplete = row["source_children"] > row["finite_children"]
        if incomplete:
            structural = construction.get((row["role"], parent))
            if structural is None or not structural["eligible"]:
                continue
            if (
                structural["task"] != row["task"]
                or structural["run_id"] != row["run_id"]
                or structural["source_size"] != row["source_children"]
            ):
                raise VerificationError("construction context mismatch")
        identity = identities[(row["role"], parent)]
        source_nodes = set(pairs[(row["role"], parent)]["nodes"]) | set(
            identity["missing_child_ids"]
        )
        if len(source_nodes) != row["source_children"] or row["status_winner"] not in source_nodes:
            raise VerificationError("source/winner closure mismatch")
        selected.append(
            {**row, "raw_parent": parent, "source_nodes": source_nodes, "winner": row["status_winner"]}
        )
    if len(selected) != protocol["expected"]["materializable_groups"]:
        raise VerificationError("selected group count mismatch")

    targets: dict[str, dict[str, dict[str, str]]] = collections.defaultdict(dict)
    for row in selected:
        for child in row["source_nodes"]:
            if child in cards:
                continue
            status_row = status.get(child)
            if status_row is None or status_row.get("status") != "UNIQUE_NODE_RECOVERED":
                raise VerificationError("missing candidate status not recovered")
            if (
                status_row.get("role") != row["role"]
                or status_row.get("expected_parent_id") != row["raw_parent"]
                or status_row.get("journal_parent_id") != row["raw_parent"]
                or status_row.get("parent_match") is not True
            ):
                raise VerificationError("missing candidate status context mismatch")
            sha = status_row.get("source_journal_sha256")
            if not isinstance(sha, str) or not HEX64.fullmatch(sha) or child in targets[sha]:
                raise VerificationError("missing candidate journal declaration invalid")
            targets[sha][child] = {
                "task": row["task"], "parent": row["raw_parent"], "role": row["role"]
            }
    recovered, inventory = recover_journal_candidates(roots, targets)

    expected_groups: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    expected_labels: dict[str, list[dict[str, Any]]] = {"frozen": [], "extension": []}
    expected_manifest: list[dict[str, Any]] = []
    provenance = collections.Counter()
    parent_card_available_by_role = collections.Counter()
    candidate_hashes: set[str] = set()
    for row in sorted(selected, key=lambda value: (value["role"], value["task"], value["parent_sha256"])):
        role = row["role"]
        parent = row["raw_parent"]
        task = row["task"]
        run = row["run_id"]
        parent_card_available_by_role[role] += int(parent in cards)
        candidates = [
            expected_card_candidate(cards, child, task, run, parent)
            if child in cards
            else recovered[child]
            for child in row["source_nodes"]
        ]
        candidates.sort(key=lambda value: value["candidate_id_sha256"])
        current = {value["candidate_id_sha256"] for value in candidates}
        if len(candidates) != row["source_children"] or len(current) != len(candidates):
            raise VerificationError("candidate set malformed")
        if candidate_hashes & current:
            raise VerificationError("candidate reused across groups")
        candidate_hashes.update(current)
        for candidate in candidates:
            provenance[candidate["provenance"]] += 1
        winner = identity_hash(row["winner"])
        if winner not in current:
            raise VerificationError("winner absent from candidate set")
        group_id = identity_hash(f"{role}\0{parent}")
        group: dict[str, Any] = {
            "schema_version": GROUP_SCHEMA,
            "group_id": group_id,
            "role": role,
            "task": task,
            "run_id_sha256": row["run_id_sha256"],
            "parent_id_sha256": row["parent_sha256"],
            "source_size": row["source_children"],
            "candidates": candidates,
        }
        if role == "train":
            group["winner_candidate_sha256"] = winner
        else:
            expected_labels[role].append(
                {
                    "schema_version": LABEL_SCHEMA,
                    "group_id": group_id,
                    "task": task,
                    "run_id_sha256": row["run_id_sha256"],
                    "winner_candidate_sha256": winner,
                }
            )
        expected_groups[role].append(group)
        expected_manifest.append(
            {
                "group_id": group_id,
                "role": role,
                "task": task,
                "run_id_sha256": row["run_id_sha256"],
                "parent_id_sha256": row["parent_sha256"],
                "source_size": row["source_children"],
                "candidate_id_sha256": [value["candidate_id_sha256"] for value in candidates],
                "candidate_code_sha256": [value["code_sha256"] for value in candidates],
                "group_payload_sha256": digest_bytes(canonical(group)),
                "winner_label_public": role == "train",
            }
        )

    public_names = {
        "train": "train_groups.jsonl",
        "frozen": "frozen_inputs.jsonl",
        "extension": "extension_inputs.jsonl",
    }
    for role, name in public_names.items():
        actual = read_jsonl(public / name, name)
        if actual != expected_groups[role]:
            raise VerificationError(f"public group reconstruction differs: {role}")
    if read_jsonl(public / "structure_manifest.jsonl", "structure manifest") != expected_manifest:
        raise VerificationError("structure manifest reconstruction differs")
    for role in ("frozen", "extension"):
        if read_jsonl(vault / f"{role}_labels.jsonl", f"{role} vault") != expected_labels[role]:
            raise VerificationError(f"sealed label reconstruction differs: {role}")

    public_hashes = {
        name: digest_file(public / name)
        for name in (*public_names.values(), "structure_manifest.jsonl")
    }
    vault_hashes = {
        f"{role}_labels.jsonl": digest_file(vault / f"{role}_labels.jsonl")
        for role in ("frozen", "extension")
    }
    role_slots = {
        role: sum(group["source_size"] for group in expected_groups[role]) for role in ROLES
    }
    role_variable = {
        role: sum(group["source_size"] >= 3 for group in expected_groups[role]) for role in ROLES
    }
    summary_expected = {
        "protocol": PROTOCOL,
        "status": "SOURCE_CHOICE_BENCHMARK_MATERIALIZED_AND_SEALED",
        "source_commit": arguments.source_commit,
        "scope": protocol["scope"],
        "groups": len(expected_manifest),
        "groups_by_role": {role: len(expected_groups[role]) for role in ROLES},
        "candidate_slots": sum(role_slots.values()),
        "candidate_slots_by_role": role_slots,
        "unique_candidate_identity_hashes": len(candidate_hashes),
        "tasks": len({row["task"] for row in expected_manifest}),
        "variable_arity_groups": sum(role_variable.values()),
        "variable_arity_groups_by_role": role_variable,
        "candidate_provenance": dict(sorted(provenance.items())),
        "choice_context": protocol["choice_context"],
        "parent_code_included": False,
        "parent_card_required": False,
        "parent_card_available_groups": sum(parent_card_available_by_role.values()),
        "parent_card_available_groups_by_role": {
            role: parent_card_available_by_role[role] for role in ROLES
        },
        "journal_inventory": inventory,
        "missing_candidates_materialized": len(recovered),
        "train_frozen_parent_overlap": 0,
        "train_frozen_run_overlap": 0,
        "frozen_public_winner_fields": 0,
        "extension_public_winner_fields": 0,
        "public_outputs": dict(public_hashes),
        "sealed_vault_outputs_opaque": vault_hashes,
        "frozen_labels_used_for_model_or_scoring": False,
        "complete_v11_choice_set_claim_allowed": False,
        "predictor_or_search_utility_claim_allowed": False,
    }
    actual_summary = object_json(public / "summary.json", "public summary")
    if actual_summary != summary_expected:
        raise VerificationError("public summary differs from independent reconstruction")
    public_hashes["summary.json"] = digest_file(public / "summary.json")
    if object_json(public / "sha256_manifest.json", "public manifest") != dict(
        sorted(public_hashes.items())
    ):
        raise VerificationError("public hash manifest mismatch")
    vault_summary_expected = {
        "protocol": PROTOCOL,
        "source_commit": arguments.source_commit,
        "labels_by_role": {role: len(expected_labels[role]) for role in ("frozen", "extension")},
        "label_file_sha256": vault_hashes,
        "labels_used_for_model_or_scoring": False,
    }
    if object_json(vault / "vault_summary.json", "vault summary") != vault_summary_expected:
        raise VerificationError("vault summary differs")
    vault_hashes["vault_summary.json"] = digest_file(vault / "vault_summary.json")
    if object_json(vault / "sha256_manifest.json", "vault manifest") != dict(
        sorted(vault_hashes.items())
    ):
        raise VerificationError("vault hash manifest mismatch")
    expected = protocol["expected"]
    if (
        summary_expected["groups"] != expected["materializable_groups"]
        or summary_expected["groups_by_role"] != expected["groups_by_role"]
        or summary_expected["candidate_slots"] != expected["candidate_slots"]
        or summary_expected["candidate_slots_by_role"] != expected["candidate_slots_by_role"]
        or summary_expected["unique_candidate_identity_hashes"]
        != expected["unique_candidate_identity_hashes"]
        or summary_expected["tasks"] != expected["tasks"]
        or summary_expected["variable_arity_groups"] != expected["variable_arity_groups"]
        or summary_expected["variable_arity_groups_by_role"]
        != expected["variable_arity_groups_by_role"]
    ):
        raise VerificationError("materialized exact count contract failed")
    return {
        "protocol": "independent-source-choice-benchmark-materialization-verifier-v2",
        "status": "INDEPENDENT_SOURCE_CHOICE_BENCHMARK_MATERIALIZATION_VERIFIED",
        "source_commit": arguments.source_commit,
        "producer_imported": "phase1.source_choice_benchmark_materializer" in sys.modules,
        "groups": summary_expected["groups"],
        "candidate_slots": summary_expected["candidate_slots"],
        "missing_candidates_materialized": summary_expected["missing_candidates_materialized"],
        "public_summary_sha256": digest_file(public / "summary.json"),
        "public_manifest_sha256": digest_file(public / "sha256_manifest.json"),
        "vault_manifest_sha256_opaque": digest_file(vault / "sha256_manifest.json"),
        "frozen_public_winner_fields": 0,
        "extension_public_winner_fields": 0,
    }


def atomic_json(path: Path, value: Any) -> None:
    if path.exists():
        raise VerificationError("verification output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
        + b"\n"
    )
    os.replace(temporary, path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--cards", required=True)
    value.add_argument("--answerability-protocol", required=True)
    value.add_argument("--per-parent", required=True)
    value.add_argument("--identity-registry", required=True)
    value.add_argument("--status-edges", required=True)
    value.add_argument("--status-registry", required=True)
    value.add_argument("--construction", required=True)
    value.add_argument("--answerability-summary", required=True)
    value.add_argument("--support-summary", required=True)
    value.add_argument("--pair", action="append", required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--public-output", required=True)
    value.add_argument("--vault-output", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        arguments = parser().parse_args()
        receipt = verify(arguments)
        if receipt["producer_imported"]:
            raise VerificationError("S1 producer imported by independent verifier")
        atomic_json(Path(arguments.output).resolve(), receipt)
        print(receipt["status"])
        return 0
    except (VerificationError, upstream.AnswerabilityError) as exc:
        print(f"SOURCE_CHOICE_BENCHMARK_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
