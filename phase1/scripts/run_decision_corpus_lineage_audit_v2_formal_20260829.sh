#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 7 ]]; then
  echo 'usage: run_decision_corpus_lineage_audit_v2_formal_20260829.sh OUTPUT_ROOT SOURCE_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
  exit 64
fi

readonly root=$1
readonly source_commit=$2
readonly protocol_sha=$3
readonly producer_sha=$4
readonly verifier_sha=$5
readonly test_sha=$6
readonly runner_sha=$7
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly protocol_rel=phase1/decision_corpus_lineage_audit_v2.json
readonly producer_rel=phase1/audit_decision_corpus_lineage_v2.py
readonly verifier_rel=phase1/verify_decision_corpus_lineage_v2.py
readonly test_rel=phase1/tests/test_decision_corpus_lineage_v2.py
readonly runner_rel=phase1/scripts/run_decision_corpus_lineage_audit_v2_formal_20260829.sh

[[ $root =~ ^/research/d7/spc/yzyang4/decision-corpus-lineage-audit-v2/formal-[A-Za-z0-9._-]+$ ]]
[[ $source_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$root"
mkdir -p "$root"
exec 9>"$root/formal.lock"
flock -n 9
printf '%s\n' "$$" >"$root/formal.pid"
failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then printf '%s\n' "$rc" >"$root/FAILED_RC" 2>/dev/null || true; fi
  exit "$rc"
}
trap failure_receipt EXIT

cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_goal=verify declared-parent lineage and deterministic parent-complete sibling quarantine for historical v11; PASS
03_population=exact Cards run map nine pair sets and published v1 receipts bound by normalized-LF SHA; PASS
04_known_before=v1 counts breadth mapped-parent counts and all-row overlap known, lineage taxonomy core support and fingerprints unseen; PASS
05_estimand=historical structural relation validity and strict-core quarantine feasibility, not predictor performance; PASS
06_variable=only Card lineage parent closure is added, with population budget split and orientation fixed; PASS
07_leakage=no prospective first960 target300 label outcome grade prediction accuracy utility or raw senior archive access; PASS
08_thresholds=four relation classes 15 hard gates six support gates and classification order frozen before readout; PASS
09_units=pair endpoint parent physical-run task and component, exact integer ratios without stochastic inference; PASS
10_resources=CPU only and one-thread caps, GPU API model-fit base-update 0/0/0/0; PASS
11_repro=public source commit exact source and input hashes two hash seeds fresh detached worktree and independent verifier; PASS
12_artifacts=aggregate JSON verification tests traces scope receipt and manifest, no row-level release; PASS
13_stop=hash schema context duplicate overlap leakage network or verifier mismatch fails closed without threshold rescue; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${source_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$source_commit" fork/phase1-value-critic
test "$(git -C "$repo" show "${source_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${source_commit}:${producer_rel}" | sha256sum | awk '{print $1}')" = "$producer_sha"
test "$(git -C "$repo" show "${source_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${source_commit}:${test_rel}" | sha256sum | awk '{print $1}')" = "$test_sha"
test "$(git -C "$repo" show "${source_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

readonly worktree=$root/worktree
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$source_commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"

export CUDA_VISIBLE_DEVICES=''
export WANDB_MODE=disabled
export PYTHONPATH="$worktree"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
unset OPENAI_API_KEY DASHSCOPE_API_KEY DEEPSEEK_API_KEY ANTHROPIC_API_KEY HF_TOKEN WANDB_API_KEY || true

"$python_bin" - "$worktree/$protocol_rel" "$repo" "$root/input_hashes_preflight.json" <<'PY'
import hashlib, json, pathlib, sys

protocol_path, data_root, output = map(pathlib.Path, sys.argv[1:])
protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

def digest(path):
    raw = path.read_bytes()
    raw.decode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()

checked = {}
inputs = protocol["immutable_inputs"]
for name in ("cards", "run_map", "v1_audit_card", "v1_independent_verification"):
    path = data_root / inputs[name]["path"]
    assert path.is_file() and not path.is_symlink()
    actual = digest(path)
    assert actual == inputs[name]["sha256"]
    checked[name] = actual
for name, metadata in sorted(inputs["pair_sets"].items()):
    path = data_root / metadata["path"]
    assert path.is_file() and not path.is_symlink()
    actual = digest(path)
    assert actual == metadata["sha256"]
    checked[name] = actual
output.write_text(json.dumps({"status": "ALL_FROZEN_INPUT_HASHES_EXACT", "count": len(checked), "hashes": checked}, sort_keys=True, indent=2) + "\n")
PY

(
  cd "$worktree"
  "$python_bin" -m py_compile "$producer_rel" "$verifier_rel" "$test_rel"
  "$python_bin" -m pytest -q "$test_rel" >"$root/focused_tests.txt"
  "$python_bin" -m pytest -q phase1/tests >"$root/full_tests.txt"
)

common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --root "$repo"
)

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/producer_a.strace" \
  "$python_bin" "$worktree/$producer_rel" "${common[@]}" \
  --source-commit "$source_commit" --output "$root/producer_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/producer_b.strace" \
  "$python_bin" "$worktree/$producer_rel" "${common[@]}" \
  --source-commit "$source_commit" --output "$root/producer_b.json"
cmp "$root/producer_a.json" "$root/producer_b.json"

verify_common=(
  "${common[@]}"
  --producer-result "$root/producer_a.json"
  --producer-script "$worktree/$producer_rel"
)
env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/verifier_a.strace" \
  "$python_bin" "$worktree/$verifier_rel" "${verify_common[@]}" --output "$root/verifier_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/verifier_b.strace" \
  "$python_bin" "$worktree/$verifier_rel" "${verify_common[@]}" --output "$root/verifier_b.json"
cmp "$root/verifier_a.json" "$root/verifier_b.json"

"$python_bin" - "$root/producer_a.json" "$root/verifier_a.json" <<'PY'
import json, pathlib, sys

p = json.loads(pathlib.Path(sys.argv[1]).read_text())
v = json.loads(pathlib.Path(sys.argv[2]).read_text())
allowed = {
    "HISTORICAL_V11_LINEAGE_AUDIT_INTEGRITY_GATE_FAIL",
    "HISTORICAL_V11_FULL_PARENT_CLOSED_DIRECT_SIBLING_CORPUS",
    "HISTORICAL_V11_LINEAGE_VERIFIED_SIBLING_CORPUS_WITH_PARENT_COMPLETE_CORE",
    "HISTORICAL_V11_PARENT_COMPLETE_SIBLING_QUARANTINE_FEASIBLE",
    "HISTORICAL_V11_PARENT_COMPLETE_SIBLING_CORE_LIMITED_SUPPORT",
}
assert p["classification"] in allowed
assert p["status"] == "HISTORICAL_V11_LINEAGE_AUDIT_COMPLETE"
assert v["status"] == "INDEPENDENTLY_VERIFIED_DECISION_CORPUS_LINEAGE_AUDIT_V2"
assert v["classification"] == p["classification"]
assert v["all_aggregate_fields_equal"] is True
assert v["imports_producer"] is False
assert p["scientific"]["hard_integrity_gate_count"]["total"] == 15
assert p["scientific"]["support_gate_count"]["total"] == 36
assert p["scope"]["pair_orientation_used"] is False
assert p["scope"]["grade_gap_label_prediction_accuracy_or_utility_used"] is False
assert p["scope"]["prospective_values_read"] is False
assert p["scope"]["raw_senior_archives_read"] is False
assert p["scope"]["row_level_release_created"] is False
assert p["scope"]["gpu_api_model_fit_base_update"] == "0/0/0/0"
PY

if grep -Ehi '/external/senior_data|prospective_decision_v1|first[-_]?960|target[-_]?300|/\.env([" ]|$)|label_vault|outcome_files|prediction[^/]*\.(json|jsonl|csv)' "$root"/*.strace* >"$root/forbidden_opens.txt"; then
  exit 87
fi
if grep -Eh 'connect\(|sendto\(|socket\(' "$root"/*.strace* >"$root/network_calls.txt"; then
  exit 88
fi

"$python_bin" - "$root" <<'PY'
import pathlib, re, sys

root = pathlib.Path(sys.argv[1])
name_re = re.compile(r"(^|[._-])(env|key|token|secret)([._-]|$)", re.I)
credential_re = re.compile(rb"(?i)(sk-[A-Za-z0-9._-]{16,}|(api[_-]?key|token|secret)\s*[:=]\s*[^\s,}\"]{8,})")
name_hits = []
content_hits = []
for path in root.rglob("*"):
    if not path.is_file() or "worktree" in path.parts:
        continue
    if name_re.search(path.name):
        name_hits.append(str(path))
    if credential_re.search(path.read_bytes()):
        content_hits.append(str(path))
assert not name_hits, name_hits
assert not content_hits, content_hits
(root / "artifact_safety_scan.txt").write_text("filename_secret_hits=0\ncredential_content_hits=0\n")
PY

printf '%s\n' \
  'prospective_first960_or_target300_values_read=false' \
  'historical_grade_gap_label_prediction_accuracy_or_utility_used=false' \
  'raw_senior_archives_opened=false' \
  'pair_orientation_used=false' \
  'row_identities_emitted=false' \
  'row_level_release_created=false' \
  'gpu_api_model_fit_base_update=0/0/0/0' >"$root/scope_receipt.txt"

find "$root" -type f ! -path "$root/worktree/*" ! -name SHA256SUMS ! -name COMPLETE -print0 \
  | sort -z | xargs -0 sha256sum >"$root/SHA256SUMS"
printf '%s\n' "$(sha256sum "$root/SHA256SUMS" | awk '{print $1}')" >"$root/MANIFEST_SHA256"
touch "$root/COMPLETE"
trap - EXIT
printf 'FORMAL_COMPLETE root=%s classification=%s manifest=%s\n' \
  "$root" \
  "$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["classification"])' "$root/producer_a.json")" \
  "$(tr -d '\r\n' <"$root/MANIFEST_SHA256")"
