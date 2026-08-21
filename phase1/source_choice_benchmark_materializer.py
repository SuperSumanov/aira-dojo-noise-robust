#!/usr/bin/env python3
"""Materialize answerability-conditioned source-choice groups and sealed labels."""

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
from typing import Any, Iterable, Sequence

from phase1 import source_decision_answerability as answerability


PROTOCOL = "source-choice-benchmark-materialization-v2"
SCHEMA = "source-choice-group-v2"
VAULT_SCHEMA = "source-choice-label-vault-v2"
ROLES = ("train", "frozen", "extension")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
CONSTRUCTION_FIELDS = (
    "role", "parent", "task", "run_id", "source_size", "eligible", "exclusion_reasons",
)
EXPECTED_SCOPE = {
    "candidate_code_bytes_used": True,
    "parent_code_used_or_emitted": False,
    "raw_journal_bytes_read_after_credential_gate": True,
    "pair_orientation_used_for_winner_label": True,
    "pair_gap_used": False,
    "numeric_grade_used": False,
    "old_hurdle_model_result_used": False,
    "prospective_outcome_used": False,
    "first960_used": False,
    "frozen_label_used_for_model_or_scoring": False,
    "gpu": 0,
    "api_calls": 0,
    "base_llm_updated": False,
}


class MaterializationError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def hash_identity(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def scan_blob(blob: bytes, where: str) -> None:
    if CREDENTIAL.search(blob):
        raise MaterializationError(f"credential-shaped bytes refused: {where}")


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise MaterializationError(f"credential-shaped bytes refused: {path.name}")
            overlap = payload[-256:]


def required_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise MaterializationError(f"invalid text: {where}")
    return value


def strict_int(value: Any, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise MaterializationError(f"invalid integer: {where}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MaterializationError(f"invalid integer: {where}") from exc
    if str(parsed) != str(value).strip() or parsed < minimum:
        raise MaterializationError(f"integer outside contract: {where}")
    return parsed


def strict_bool(value: Any, where: str) -> bool:
    if value in (True, "True"):
        return True
    if value in (False, "False"):
        return False
    raise MaterializationError(f"invalid boolean: {where}")


def load_json(path: Path, where: str) -> dict[str, Any]:
    scan_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MaterializationError(f"invalid JSON: {where}") from exc
    if not isinstance(value, dict):
        raise MaterializationError(f"JSON object required: {where}")
    return value


def load_protocol(path: Path) -> dict[str, Any]:
    value = load_json(path, "materialization protocol")
    if value.get("protocol") != PROTOCOL:
        raise MaterializationError("materialization protocol mismatch")
    inputs = value.get("inputs")
    expected = value.get("expected")
    if not isinstance(inputs, dict) or not inputs or any(
        not isinstance(item, str) or not SHA256.fullmatch(item) for item in inputs.values()
    ):
        raise MaterializationError("invalid input digest map")
    if not isinstance(expected, dict):
        raise MaterializationError("missing exact expected counts")
    for name in (
        "cards", "parents", "status_winners", "materializable_groups", "candidate_slots",
        "unique_candidate_identity_hashes",
        "tasks", "variable_arity_groups", "status_registry_rows", "construction_rows",
        "eligible_construction_rows",
    ):
        if isinstance(expected.get(name), bool) or not isinstance(expected.get(name), int) or expected[name] <= 0:
            raise MaterializationError(f"invalid exact count: {name}")
    for name in (
        "groups_by_role", "candidate_slots_by_role", "variable_arity_groups_by_role",
        "construction_rows_by_role", "eligible_construction_rows_by_role",
    ):
        counts = expected.get(name)
        if not isinstance(counts, dict) or set(counts) != set(ROLES) or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in counts.values()
        ):
            raise MaterializationError(f"invalid role map: {name}")
    if sum(expected["groups_by_role"].values()) != expected["materializable_groups"]:
        raise MaterializationError("group role map does not close")
    if sum(expected["candidate_slots_by_role"].values()) != expected["candidate_slots"]:
        raise MaterializationError("candidate role map does not close")
    if sum(expected["variable_arity_groups_by_role"].values()) != expected["variable_arity_groups"]:
        raise MaterializationError("variable-arity role map does not close")
    if sum(expected["construction_rows_by_role"].values()) != expected["construction_rows"]:
        raise MaterializationError("construction role map does not close")
    if sum(expected["eligible_construction_rows_by_role"].values()) != expected[
        "eligible_construction_rows"
    ]:
        raise MaterializationError("eligible construction role map does not close")
    aliases = value.get("journal_root_aliases")
    if not isinstance(aliases, list) or len(aliases) != len(set(aliases)) or any(
        not isinstance(alias, str) or not re.fullmatch(r"[a-z0-9_]+", alias) for alias in aliases
    ):
        raise MaterializationError("invalid journal aliases")
    if value.get("candidate_order") != "ascending_sha256_of_raw_candidate_id":
        raise MaterializationError("candidate order contract drifted")
    if value.get("choice_context") != "task_run_parent_hash_plus_candidate_code_only":
        raise MaterializationError("choice context contract drifted")
    if value.get("parent_code_included") is not False or value.get("parent_card_required") is not False:
        raise MaterializationError("parent context was reintroduced")
    if value.get("frozen_label_policy") != "separate_opaque_read_only_vault":
        raise MaterializationError("frozen label policy drifted")
    if value.get("allow_result_rescue") is not False or value.get("scope") != EXPECTED_SCOPE:
        raise MaterializationError("scope or rescue contract drifted")
    return value


def parse_roots(values: Sequence[str], protocol: dict[str, Any]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise MaterializationError("journal root must be ALIAS=PATH")
        alias, raw_path = value.split("=", 1)
        if alias in roots or not re.fullmatch(r"[a-z0-9_]+", alias):
            raise MaterializationError("invalid or duplicate journal alias")
        path = Path(raw_path).resolve()
        if not path.is_dir():
            raise MaterializationError(f"journal root missing: {alias}")
        roots[alias] = path
    if sorted(roots) != sorted(protocol["journal_root_aliases"]):
        raise MaterializationError("journal root aliases differ from protocol")
    return roots


def verify_input_hash(path: Path, expected: str, where: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise MaterializationError(f"input hash mismatch: {where}")


def load_construction(path: Path, protocol: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    scan_file(path)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    role_counts: collections.Counter[str] = collections.Counter()
    eligible_counts: collections.Counter[str] = collections.Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CONSTRUCTION_FIELDS:
            raise MaterializationError("construction schema mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = required_text(raw.get("role"), f"construction {line_number}:role")
            parent = required_text(raw.get("parent"), f"construction {line_number}:parent")
            task = required_text(raw.get("task"), f"construction {line_number}:task")
            run_id = required_text(raw.get("run_id"), f"construction {line_number}:run")
            if role not in ROLES or (role, parent) in rows:
                raise MaterializationError(f"invalid construction identity: {line_number}")
            eligible = strict_bool(raw.get("eligible"), f"construction {line_number}:eligible")
            reasons = str(raw.get("exclusion_reasons") or "")
            if eligible and reasons:
                raise MaterializationError(f"eligible construction row has exclusion: {line_number}")
            rows[(role, parent)] = {
                "role": role,
                "parent": parent,
                "task": task,
                "run_id": run_id,
                "source_size": strict_int(raw.get("source_size"), f"construction {line_number}:size", 2),
                "eligible": eligible,
            }
            role_counts[role] += 1
            eligible_counts[role] += int(eligible)
    expected = protocol["expected"]
    if len(rows) != expected["construction_rows"] or {
        role: role_counts[role] for role in ROLES
    } != expected["construction_rows_by_role"]:
        raise MaterializationError("construction counts mismatch")
    if sum(eligible_counts.values()) != expected["eligible_construction_rows"] or {
        role: eligible_counts[role] for role in ROLES
    } != expected["eligible_construction_rows_by_role"]:
        raise MaterializationError("eligible construction counts mismatch")
    return rows


def load_status_registry(path: Path, protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scan_file(path)
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MaterializationError(f"status registry JSON invalid: {line_number}") from exc
            if not isinstance(raw, dict):
                raise MaterializationError(f"status registry row invalid: {line_number}")
            child = required_text(raw.get("child_id"), f"status {line_number}:child")
            if child in rows:
                raise MaterializationError(f"duplicate status child: {line_number}")
            rows[child] = raw
    if len(rows) != protocol["expected"]["status_registry_rows"]:
        raise MaterializationError("status registry row count mismatch")
    return rows


def load_cards(path: Path, protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scan_file(path)
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MaterializationError(f"cards JSON invalid: {line_number}") from exc
            if not isinstance(raw, dict):
                raise MaterializationError(f"card row invalid: {line_number}")
            card_id = required_text(raw.get("id"), f"card {line_number}:id")
            if card_id in rows:
                raise MaterializationError(f"duplicate card id: {line_number}")
            rows[card_id] = raw
    if len(rows) != protocol["expected"]["cards"]:
        raise MaterializationError("cards row count mismatch")
    return rows


def canonical_journals(root: Path) -> list[Path]:
    by_run: dict[Path, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.name.lower() != "journal.jsonl":
            continue
        run_dir = path.parent.parent
        current = by_run.get(run_dir)
        if current is None or ("checkpoint" in path.parts and "checkpoint" not in current.parts):
            by_run[run_dir] = path
    return [by_run[key] for key in sorted(by_run, key=lambda item: item.as_posix())]


def collect_needed_journals(
    roots: dict[str, Path], needed: set[str]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    found: dict[str, bytes] = {}
    scanned = credential_skipped = 0
    canonical_counts: dict[str, int] = {}
    for alias, root in sorted(roots.items()):
        journals = canonical_journals(root)
        canonical_counts[alias] = len(journals)
        for journal in journals:
            blob = journal.read_bytes()
            scanned += 1
            digest = sha256_bytes(blob)
            credential = CREDENTIAL.search(blob) is not None
            if credential:
                credential_skipped += 1
                if digest in needed:
                    raise MaterializationError("needed journal contains credential-shaped bytes")
                continue
            if digest in needed:
                previous = found.get(digest)
                if previous is not None and previous != blob:
                    raise MaterializationError("SHA collision across needed journals")
                found[digest] = blob
    if set(found) != needed:
        raise MaterializationError("needed journal SHA closure failed")
    return found, {
        "canonical_journals_by_root": dict(sorted(canonical_counts.items())),
        "journal_files_scanned": scanned,
        "credential_shape_journals_skipped": credential_skipped,
        "needed_journal_shas": len(needed),
        "needed_journal_shas_found": len(found),
    }


def node_card_id(task: str, node: dict[str, Any]) -> str:
    raw = node.get("id", node.get("step"))
    if raw is None:
        raise MaterializationError("journal node lacks id and step")
    return f"{task}__{raw}"


def decode_needed_nodes(
    blobs: dict[str, bytes], targets_by_sha: dict[str, dict[str, dict[str, str]]]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for journal_sha in sorted(blobs):
        blob = blobs[journal_sha]
        scan_blob(blob, journal_sha)
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MaterializationError("needed journal is not UTF-8") from exc
        nodes: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                node = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MaterializationError(f"needed journal JSON invalid: {journal_sha}:{line_number}") from exc
            if not isinstance(node, dict):
                raise MaterializationError("needed journal row is not an object")
            nodes.append(node)
        task_values = {
            str(metric["competition_id"])
            for node in nodes
            if isinstance((metric := node.get("metric_info")), dict) and metric.get("competition_id")
        }
        if len(task_values) != 1:
            raise MaterializationError("needed journal task identity is ambiguous")
        task = next(iter(task_values))
        by_step: dict[Any, dict[str, Any]] = {}
        for node in nodes:
            step = node.get("step")
            if step in by_step:
                raise MaterializationError("duplicate journal step")
            by_step[step] = node
        expected = targets_by_sha[journal_sha]
        seen: set[str] = set()
        for node in nodes:
            child = node_card_id(task, node)
            if child not in expected:
                continue
            if child in seen:
                raise MaterializationError("duplicate target child in needed journal")
            seen.add(child)
            context = expected[child]
            if context["task"] != task:
                raise MaterializationError("journal task differs from target context")
            parents = node.get("parents") or []
            if not isinstance(parents, list) or len(parents) != 1 or parents[0] not in by_step:
                raise MaterializationError("target journal node lacks unique parent")
            parent_id = node_card_id(task, by_step[parents[0]])
            if parent_id != context["parent"]:
                raise MaterializationError("target journal parent mismatch")
            code = node.get("code")
            if not isinstance(code, str) or not code:
                raise MaterializationError("target journal code absent")
            operators = node.get("operators_used") or []
            operator = operators[0] if isinstance(operators, list) and operators else "Draft"
            step = strict_int(node.get("step"), "journal target step")
            depth_value = node.get("depth")
            depth = strict_int(depth_value if depth_value is not None else len(parents), "journal target depth")
            output[child] = {
                "candidate_id_sha256": hash_identity(child),
                "code": code,
                "code_sha256": sha256_bytes(code.encode("utf-8")),
                "operator": str(operator),
                "step": step,
                "depth": depth,
                "provenance": "journal_recovered",
                "source_journal_sha256": journal_sha,
            }
        if seen != set(expected):
            raise MaterializationError("needed journal target closure failed")
    if len(output) != sum(len(value) for value in targets_by_sha.values()):
        raise MaterializationError("decoded journal target total mismatch")
    return output


def card_context(card: dict[str, Any], card_id: str) -> tuple[str, str, dict[str, Any]]:
    task_value = card.get("task")
    task = required_text(
        task_value.get("name") if isinstance(task_value, dict) else None, f"card task: {hash_identity(card_id)}"
    )
    run_id = required_text(card.get("run_id"), f"card run: {hash_identity(card_id)}")
    lineage = card.get("lineage")
    if not isinstance(lineage, dict):
        raise MaterializationError(f"card lineage absent: {hash_identity(card_id)}")
    return task, run_id, lineage


def card_candidate(
    cards: dict[str, dict[str, Any]], child: str, task: str, run_id: str, parent: str
) -> dict[str, Any]:
    card = cards.get(child)
    if card is None:
        raise MaterializationError("retained candidate absent from cards")
    actual_task, actual_run, lineage = card_context(card, child)
    if actual_task != task or actual_run != run_id or lineage.get("parent_id") != parent:
        raise MaterializationError("retained candidate context mismatch")
    code = card.get("code")
    if not isinstance(code, str) or not code:
        raise MaterializationError("retained candidate code absent")
    operator = lineage.get("op")
    if not isinstance(operator, str) or not operator:
        raise MaterializationError("retained candidate operator absent")
    step = strict_int(lineage.get("step"), "retained candidate step")
    depth_raw = lineage.get("depth", lineage.get("tree_depth"))
    depth = strict_int(depth_raw, "retained candidate depth")
    return {
        "candidate_id_sha256": hash_identity(child),
        "code": code,
        "code_sha256": sha256_bytes(code.encode("utf-8")),
        "operator": operator,
        "step": step,
        "depth": depth,
        "provenance": "card",
        "source_journal_sha256": None,
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> tuple[int, str]:
    count = 0
    digest = hashlib.sha256()
    with path.open("wb") as handle:
        for row in rows:
            payload = canonical_json(row) + b"\n"
            handle.write(payload)
            digest.update(payload)
            count += 1
    return count, digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.write_bytes(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def build(arguments: argparse.Namespace) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.source_commit):
        raise MaterializationError("source commit must be full lowercase SHA-1")
    protocol_path = Path(arguments.protocol).resolve()
    protocol = load_protocol(protocol_path)
    paths = {
        "cards": Path(arguments.cards).resolve(),
        "answerability_module": Path(answerability.__file__).resolve(),
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
        verify_input_hash(path, protocol["inputs"][f"{name}_sha256"], name)
        scan_file(path)
    roots = parse_roots(arguments.root, protocol)
    public_output = Path(arguments.public_output).resolve()
    vault_output = Path(arguments.vault_output).resolve()
    public_staging = public_output.with_name(public_output.name + f".tmp-{os.getpid()}")
    vault_staging = vault_output.with_name(vault_output.name + f".tmp-{os.getpid()}")
    if any(path.exists() for path in (public_output, vault_output, public_staging, vault_staging)):
        raise MaterializationError("output or staging path already exists")

    upstream_protocol = answerability.load_protocol(paths["answerability_protocol"])
    parents = answerability.load_parents(paths["per_parent"], upstream_protocol)
    identities = answerability.load_identity(paths["identity_registry"], upstream_protocol, parents)
    pair_paths = answerability.parse_pair_arguments(arguments.pair)
    pairs = answerability.load_pairs(pair_paths, upstream_protocol, parents)
    status_edges = answerability.load_status_edges(
        paths["status_edges"], upstream_protocol, parents, identities, pairs
    )
    answer_rows = answerability.build_parent_rows(parents, identities, pairs, status_edges)
    if len(answer_rows) != protocol["expected"]["parents"] or sum(
        row["status_winner"] is not None for row in answer_rows
    ) != protocol["expected"]["status_winners"]:
        raise MaterializationError("answerability reconstruction counts mismatch")
    answer_summary = load_json(paths["answerability_summary"], "answerability summary")
    support_summary = load_json(paths["support_summary"], "support summary")
    if answer_summary.get("status") != "VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY":
        raise MaterializationError("answerability summary status mismatch")
    if support_summary.get("status") != "SOURCE_CHOICE_MATERIALIZATION_SUPPORT_FEASIBLE":
        raise MaterializationError("support summary status mismatch")

    construction = load_construction(paths["construction"], protocol)
    status_registry = load_status_registry(paths["status_registry"], protocol)
    cards = load_cards(paths["cards"], protocol)
    parent_by_hash: dict[tuple[str, str], str] = {}
    for role, parent in parents:
        key = (role, hash_identity(parent))
        if key in parent_by_hash:
            raise MaterializationError("parent identity hash collision")
        parent_by_hash[key] = parent

    selected: list[dict[str, Any]] = []
    for row in answer_rows:
        winner = row["status_winner"]
        if winner is None:
            continue
        raw_parent = parent_by_hash.get((row["role"], row["parent_sha256"]))
        if raw_parent is None:
            raise MaterializationError("answerability parent hash has no raw identity")
        incomplete = row["source_children"] > row["finite_children"]
        if incomplete:
            structural = construction.get((row["role"], raw_parent))
            if structural is None or not structural["eligible"]:
                continue
            if (
                structural["task"] != row["task"]
                or structural["run_id"] != row["run_id"]
                or structural["source_size"] != row["source_children"]
            ):
                raise MaterializationError("selected construction context mismatch")
        identity = identities[(row["role"], raw_parent)]
        source_nodes = set(pairs[(row["role"], raw_parent)]["nodes"]) | set(identity["missing_child_ids"])
        if len(source_nodes) != row["source_children"] or winner not in source_nodes:
            raise MaterializationError("selected source/winner closure failed")
        selected.append({**row, "raw_parent": raw_parent, "source_nodes": source_nodes, "winner": winner})

    role_counts = collections.Counter(row["role"] for row in selected)
    if len(selected) != protocol["expected"]["materializable_groups"] or {
        role: role_counts[role] for role in ROLES
    } != protocol["expected"]["groups_by_role"]:
        raise MaterializationError("selected group counts mismatch")

    targets_by_sha: dict[str, dict[str, dict[str, str]]] = collections.defaultdict(dict)
    for row in selected:
        for child in sorted(row["source_nodes"]):
            if child in cards:
                continue
            status = status_registry.get(child)
            if status is None or status.get("status") != "UNIQUE_NODE_RECOVERED":
                raise MaterializationError("selected missing candidate status unavailable")
            if (
                status.get("role") != row["role"]
                or status.get("expected_parent_id") != row["raw_parent"]
                or status.get("journal_parent_id") != row["raw_parent"]
                or status.get("parent_match") is not True
            ):
                raise MaterializationError("selected missing candidate status context mismatch")
            journal_sha = status.get("source_journal_sha256")
            if not isinstance(journal_sha, str) or not SHA256.fullmatch(journal_sha):
                raise MaterializationError("selected missing candidate journal SHA absent")
            if child in targets_by_sha[journal_sha]:
                raise MaterializationError("duplicate missing target declaration")
            targets_by_sha[journal_sha][child] = {
                "parent": row["raw_parent"], "task": row["task"], "role": row["role"]
            }

    blobs, journal_inventory = collect_needed_journals(roots, set(targets_by_sha))
    recovered = decode_needed_nodes(blobs, targets_by_sha)
    groups: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    vaults: dict[str, list[dict[str, Any]]] = {"frozen": [], "extension": []}
    manifest_rows: list[dict[str, Any]] = []
    provenance_counts: collections.Counter[str] = collections.Counter()
    parent_card_available_by_role: collections.Counter[str] = collections.Counter()
    seen_group_ids: set[str] = set()
    all_candidate_ids: set[str] = set()

    for row in sorted(selected, key=lambda item: (item["role"], item["task"], item["parent_sha256"])):
        role = row["role"]
        raw_parent = row["raw_parent"]
        parent_card_available_by_role[role] += int(raw_parent in cards)

        candidates: list[dict[str, Any]] = []
        raw_by_hash: dict[str, str] = {}
        for child in row["source_nodes"]:
            candidate = (
                card_candidate(cards, child, row["task"], row["run_id"], raw_parent)
                if child in cards
                else recovered[child]
            )
            candidate_hash = candidate["candidate_id_sha256"]
            if candidate_hash in raw_by_hash and raw_by_hash[candidate_hash] != child:
                raise MaterializationError("candidate identity hash collision")
            raw_by_hash[candidate_hash] = child
            candidates.append(candidate)
            provenance_counts[candidate["provenance"]] += 1
        candidates.sort(key=lambda item: item["candidate_id_sha256"])
        if len(candidates) != row["source_children"] or len({item["candidate_id_sha256"] for item in candidates}) != len(candidates):
            raise MaterializationError("candidate group closure failed")
        winner_hash = hash_identity(row["winner"])
        if winner_hash not in {item["candidate_id_sha256"] for item in candidates}:
            raise MaterializationError("winner not in materialized candidate set")
        group_id = hash_identity(f"{role}\0{raw_parent}")
        if group_id in seen_group_ids:
            raise MaterializationError("duplicate group id")
        seen_group_ids.add(group_id)
        current_candidate_ids = {item["candidate_id_sha256"] for item in candidates}
        if all_candidate_ids & current_candidate_ids:
            raise MaterializationError("candidate identity reused across source groups")
        all_candidate_ids.update(current_candidate_ids)
        group: dict[str, Any] = {
            "schema_version": SCHEMA,
            "group_id": group_id,
            "role": role,
            "task": row["task"],
            "run_id_sha256": row["run_id_sha256"],
            "parent_id_sha256": row["parent_sha256"],
            "source_size": row["source_children"],
            "candidates": candidates,
        }
        if role == "train":
            group["winner_candidate_sha256"] = winner_hash
        else:
            vaults[role].append(
                {
                    "schema_version": VAULT_SCHEMA,
                    "group_id": group_id,
                    "task": row["task"],
                    "run_id_sha256": row["run_id_sha256"],
                    "winner_candidate_sha256": winner_hash,
                }
            )
        groups[role].append(group)
        manifest_rows.append(
            {
                "group_id": group_id,
                "role": role,
                "task": row["task"],
                "run_id_sha256": row["run_id_sha256"],
                "parent_id_sha256": row["parent_sha256"],
                "source_size": row["source_children"],
                "candidate_id_sha256": [item["candidate_id_sha256"] for item in candidates],
                "candidate_code_sha256": [item["code_sha256"] for item in candidates],
                "group_payload_sha256": sha256_bytes(canonical_json(group)),
                "winner_label_public": role == "train",
            }
        )

    candidate_by_role = {role: sum(row["source_size"] for row in groups[role]) for role in ROLES}
    variable_by_role = {role: sum(row["source_size"] >= 3 for row in groups[role]) for role in ROLES}
    if candidate_by_role != protocol["expected"]["candidate_slots_by_role"]:
        raise MaterializationError("candidate slot counts mismatch")
    if variable_by_role != protocol["expected"]["variable_arity_groups_by_role"]:
        raise MaterializationError("variable-arity counts mismatch")
    if len({row["task"] for row in manifest_rows}) != protocol["expected"]["tasks"]:
        raise MaterializationError("task count mismatch")
    if len(all_candidate_ids) != protocol["expected"]["unique_candidate_identity_hashes"]:
        raise MaterializationError("unique candidate identity count mismatch")
    train_parent = {row["parent_id_sha256"] for row in manifest_rows if row["role"] == "train"}
    frozen_parent = {row["parent_id_sha256"] for row in manifest_rows if row["role"] == "frozen"}
    train_run = {row["run_id_sha256"] for row in manifest_rows if row["role"] == "train"}
    frozen_run = {row["run_id_sha256"] for row in manifest_rows if row["role"] == "frozen"}
    if train_parent & frozen_parent or train_run & frozen_run:
        raise MaterializationError("train/frozen identity overlap")

    public_staging.mkdir(parents=True)
    vault_staging.mkdir(parents=True)
    public_files = {
        "train_groups.jsonl": groups["train"],
        "frozen_inputs.jsonl": groups["frozen"],
        "extension_inputs.jsonl": groups["extension"],
        "structure_manifest.jsonl": manifest_rows,
    }
    public_hashes: dict[str, str] = {}
    for name, values in public_files.items():
        count, digest = write_jsonl(public_staging / name, values)
        if count != len(values):
            raise MaterializationError("public output row count mismatch")
        public_hashes[name] = digest
    vault_hashes: dict[str, str] = {}
    for role in ("frozen", "extension"):
        name = f"{role}_labels.jsonl"
        count, digest = write_jsonl(vault_staging / name, vaults[role])
        if count != len(vaults[role]):
            raise MaterializationError("vault output row count mismatch")
        vault_hashes[name] = digest
        os.chmod(vault_staging / name, 0o400)

    summary = {
        "protocol": PROTOCOL,
        "status": "SOURCE_CHOICE_BENCHMARK_MATERIALIZED_AND_SEALED",
        "source_commit": arguments.source_commit,
        "scope": protocol["scope"],
        "groups": len(manifest_rows),
        "groups_by_role": {role: len(groups[role]) for role in ROLES},
        "candidate_slots": sum(candidate_by_role.values()),
        "candidate_slots_by_role": candidate_by_role,
        "unique_candidate_identity_hashes": len(all_candidate_ids),
        "tasks": len({row["task"] for row in manifest_rows}),
        "variable_arity_groups": sum(variable_by_role.values()),
        "variable_arity_groups_by_role": variable_by_role,
        "candidate_provenance": dict(sorted(provenance_counts.items())),
        "choice_context": protocol["choice_context"],
        "parent_code_included": False,
        "parent_card_required": False,
        "parent_card_available_groups": sum(parent_card_available_by_role.values()),
        "parent_card_available_groups_by_role": {
            role: parent_card_available_by_role[role] for role in ROLES
        },
        "journal_inventory": journal_inventory,
        "missing_candidates_materialized": len(recovered),
        "train_frozen_parent_overlap": 0,
        "train_frozen_run_overlap": 0,
        "frozen_public_winner_fields": sum("winner_candidate_sha256" in row for row in groups["frozen"]),
        "extension_public_winner_fields": sum(
            "winner_candidate_sha256" in row for row in groups["extension"]
        ),
        "public_outputs": dict(public_hashes),
        "sealed_vault_outputs_opaque": vault_hashes,
        "frozen_labels_used_for_model_or_scoring": False,
        "complete_v11_choice_set_claim_allowed": False,
        "predictor_or_search_utility_claim_allowed": False,
    }
    atomic_json(public_staging / "summary.json", summary)
    public_hashes["summary.json"] = sha256_file(public_staging / "summary.json")
    atomic_json(public_staging / "sha256_manifest.json", dict(sorted(public_hashes.items())))
    atomic_json(
        vault_staging / "vault_summary.json",
        {
            "protocol": PROTOCOL,
            "source_commit": arguments.source_commit,
            "labels_by_role": {role: len(vaults[role]) for role in ("frozen", "extension")},
            "label_file_sha256": vault_hashes,
            "labels_used_for_model_or_scoring": False,
        },
    )
    vault_hashes["vault_summary.json"] = sha256_file(vault_staging / "vault_summary.json")
    atomic_json(vault_staging / "sha256_manifest.json", dict(sorted(vault_hashes.items())))
    os.chmod(vault_staging / "vault_summary.json", 0o400)
    os.chmod(vault_staging / "sha256_manifest.json", 0o400)
    for path in list(public_staging.iterdir()) + list(vault_staging.iterdir()):
        scan_file(path)
    public_staging.replace(public_output)
    vault_staging.replace(vault_output)
    return summary


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
    return value


def main() -> int:
    try:
        summary = build(parser().parse_args())
        print(
            f"SOURCE_CHOICE_BENCHMARK_MATERIALIZED groups={summary['groups']} "
            f"candidates={summary['candidate_slots']}"
        )
        return 0
    except (MaterializationError, answerability.AnswerabilityError) as exc:
        print(f"SOURCE_CHOICE_BENCHMARK_MATERIALIZATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
