#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 7 ]]; then
  echo 'usage: run_historical_run_split_breadth_pareto_formal_20260829.sh OUTPUT_ROOT CONTROL_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
  exit 64
fi

readonly root=$1
readonly control_commit=$2
readonly protocol_sha=$3
readonly producer_sha=$4
readonly verifier_sha=$5
readonly test_sha=$6
readonly runner_sha=$7
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly data_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/input-f534114-v3
readonly cards_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/cards-f534114-v1
readonly protocol_rel=phase1/historical_run_split_breadth_pareto_falsification_v1.json
readonly producer_rel=phase1/falsify_historical_run_split_breadth_pareto.py
readonly verifier_rel=phase1/verify_historical_run_split_breadth_pareto.py
readonly test_rel=phase1/tests/test_historical_run_split_breadth_pareto.py
readonly runner_rel=phase1/scripts/run_historical_run_split_breadth_pareto_formal_20260829.sh
readonly prior_protocol_rel=phase1/historical_independent_label_scarce_yield_confirmation_v1.json
readonly prior_producer_rel=phase1/confirm_historical_independent_label_scarce_yield.py
readonly prior_verifier_rel=phase1/verify_historical_independent_label_scarce_yield.py
readonly prior_package=phase1/results/historical_independent_label_scarce_yield_20260829_c7148fb
readonly qualification_protocol_rel=phase1/historical_independent_sibling_graph_gate_v1.json
readonly qualification_package=phase1/results/historical_independent_sibling_graph_gate_20260829_7ad83d2
readonly qualification_producer_rel=phase1/audit_historical_independent_sibling_graph_gate.py
readonly qualification_verifier_rel=phase1/verify_historical_independent_sibling_graph_gate.py
readonly acquisition_producer_rel=phase1/tree_node_label_yield.py
readonly acquisition_verifier_rel=phase1/verify_tree_node_label_yield.py
readonly v11_rel=phase1/v11_decision/decision_train_v11_b0.jsonl
readonly lineage_rel=phase1/results/decision_corpus_lineage_audit_v2_20260829_2514842/formal/producer_a.json
readonly senior_protocol_rel=phase1/senior_0819_verified_sibling_quarantine_v1.json
readonly senior_package=phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80

[[ $root =~ ^/research/d7/spc/yzyang4/historical-run-split-breadth-pareto/formal-[A-Za-z0-9._-]+$ ]]
[[ $control_commit =~ ^[0-9a-f]{40}$ ]]
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
  if (( rc != 0 )); then
    printf '%s\n' "$rc" >"$root/FAILED_RC" 2>/dev/null || true
  fi
  exit "$rc"
}
trap failure_receipt EXIT

cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_goal=falsify whether the post-readout yield-noninferior task/run-breadth Pareto pattern survives in both deterministic physical-run-disjoint halves; PASS
03_context=the full-graph yield-confirmation failure and descriptive breadth pattern are disclosed; this is internal falsification and never external confirmation; PASS
04_known_before=full 539-pair aggregate and full-graph curves known; hash-run split counts support profiles and fold curves unseen; PASS
05_population=exact prior 539-pair strict residual split only by physical-run SHA256 parity; senior test rows forbidden; PASS
06_estimand=per-fold six-checkpoint yield noninferiority plus task/run breadth superiority and parent breadth preservation; no accuracy or search utility; PASS
07_controls=balanced-closure greedy versus strong uniform-edge on the same fold topology endpoint budgets and nested trajectory contract; PASS
08_thresholds=fold support plus yield 1 and 5/6 task 6/5 run 11/10 parent 9/10 and anti-dominance all fixed in both folds with no rescue; PASS
09_randomness=256 uniform randomizations and 32 greedy tie trajectories fixed by SHA256; producer and independent verifier repeated under hash seeds 0 and 1; PASS
10_resources=CPU only with one-thread caps; GPU API model-fit base-update 0/0/0/0; PASS
11_leakage=no orientation gap grade outcome code prediction runtime senior test or prospective first960 target300 target522 value use; PASS
12_security=credential receipt checked before safe Cards parse; raw senior archives and identity release forbidden; PASS
13_stop=any hash certificate manifest verifier or scanner failure exits before COMPLETE; overlap gets the frozen integrity class and support failure gets the frozen limited-support class with no curves; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${control_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$control_commit" fork/phase1-value-critic
test "$(git -C "$repo" show "${control_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${control_commit}:${producer_rel}" | sha256sum | awk '{print $1}')" = "$producer_sha"
test "$(git -C "$repo" show "${control_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${control_commit}:${test_rel}" | sha256sum | awk '{print $1}')" = "$test_sha"
test "$(git -C "$repo" show "${control_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

test "$(sha256sum "$data_root/decision.jsonl" | awk '{print $1}')" = 1a01d3a1202b35f21b9cd6c87237b29c50b1c293138b407cc453674108411442
test "$(sha256sum "$data_root/runsplit_holdruns.json" | awk '{print $1}')" = 593117cfe0b34e1d2e3c9b718866a7751d7f008701add77b31cfd604282103bb
test "$(sha256sum "$cards_root/cards.safe.json" | awk '{print $1}')" = 5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343
test "$(sha256sum "$cards_root/security_scan.json" | awk '{print $1}')" = d41142279bdba7db4495664df6836eecec3a36016cd316164ee5e54d4518eccc
"$python_bin" - "$cards_root/security_scan.json" <<'PY'
import json
import pathlib
import sys

value = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert value["status"] == "CREDENTIAL_SCAN_AND_REDACTION_PASS"
assert value["input_sha256"] == value["safe_sha256"] == "5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343"
assert value["remaining_credential_hits"] == value["private_key_markers"] == 0
assert value["json_parsed_before_scan"] is False
PY

readonly worktree=$root/worktree
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$control_commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"

test "$(sha256sum "$worktree/$prior_protocol_rel" | awk '{print $1}')" = 69db0331c92f5912dfb5fcd6ebc3dfeb0838eff090f80390e2137c91bd489581
test "$(sha256sum "$worktree/$prior_producer_rel" | awk '{print $1}')" = 3195b7499a1a10ad8e4e3f8faa586d3bc92314589dcb88c7e4f6157be912a78d
test "$(sha256sum "$worktree/$prior_verifier_rel" | awk '{print $1}')" = ea72412b072f693045089daef1f37bfcdd672f563d6cd7ff1392bbe1e00ccfa7
test "$(sha256sum "$worktree/$prior_package/aggregate_result.json" | awk '{print $1}')" = aea7a45b1ad3c7213cf90a508e4e0bba42ba72bfdd4ca9fca539e309d953622d
test "$(sha256sum "$worktree/$prior_package/independent_verification.json" | awk '{print $1}')" = 13b70a87b4d6c4a49091a1684dc2ab0dec5fc8c064d7c994b7f2b2236c431d63
test "$(sha256sum "$worktree/$prior_package/SHA256SUMS" | awk '{print $1}')" = b93fcc8240329ee743b5f178da3a06d47cbb69b5f5226f76616696542492a5fc
(
  cd "$worktree/$prior_package"
  sha256sum -c SHA256SUMS >"$root/prior_package_manifest_check.txt"
)

test "$(sha256sum "$worktree/$qualification_protocol_rel" | awk '{print $1}')" = b033ddbe99c94a0e9e924233181879121e8a3f2021d86278210f58d1fa720c4c
test "$(sha256sum "$worktree/$qualification_package/formal_summary.json" | awk '{print $1}')" = ea66df81b640c8623936c40bd2742245361c684f6d270ef53b59f4432e65fa18
test "$(sha256sum "$worktree/$qualification_package/verification.json" | awk '{print $1}')" = 6f7c3a3ca782e4d18d9d67ee6954f0a6bcbbafedac0d1a134a1b1fdfa6e0c8a1
test "$(sha256sum "$worktree/$qualification_package/SHA256SUMS" | awk '{print $1}')" = 8478d0e4ae71cf73f789d470540ed6065f0a81cea5c9ac76263629e86d0f85bf
(
  cd "$worktree/$qualification_package"
  sha256sum -c SHA256SUMS >"$root/qualification_package_manifest_check.txt"
)
test "$(sha256sum "$worktree/$lineage_rel" | awk '{print $1}')" = 23e9a8139be60ee4c34d3c44eda9afaed3034a68f6749ebcb0555c10a15f0032
test "$(sha256sum "$worktree/$senior_protocol_rel" | awk '{print $1}')" = f4d09f1203ba72181046ac620862eb10351736cd01a25ac3597b21e4b931b680
test "$(sha256sum "$worktree/$senior_package/formal_summary.json" | awk '{print $1}')" = 4f4902ce365523b01a0cca1eadb716b978aa0771d15286be1bf4aecca6456315
test "$(sha256sum "$worktree/$senior_package/verification.json" | awk '{print $1}')" = 8b0eb84365aa3cb16bfd3b9a4ca3affabfc4fd24774071a6cbba366b88f57ca0
test "$(sha256sum "$worktree/$senior_package/MANIFEST.sha256" | awk '{print $1}')" = 3f6202fb14b044a23fbcae722c0c38ab48253bbd5ac9ebe2b4b011f3b7f84a28
(
  cd "$worktree/$senior_package"
  sha256sum -c MANIFEST.sha256 >"$root/senior_package_manifest_check.txt"
)

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
unset OPENAI_API_KEY OPENROUTER_API_KEY DASHSCOPE_API_KEY DEEPSEEK_API_KEY ANTHROPIC_API_KEY HF_TOKEN WANDB_API_KEY || true

(
  cd "$worktree"
  "$python_bin" -m pytest -q "$test_rel" phase1/tests/test_historical_independent_label_scarce_yield.py \
    phase1/tests/test_tree_node_label_yield.py phase1/tests/test_historical_independent_sibling_graph_gate.py \
    phase1/tests/test_verify_historical_independent_sibling_graph_gate.py >"$root/focused_tests.txt"
  "$python_bin" -m pytest -q phase1/tests >"$root/full_tests.txt"
)

producer_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --prior-protocol "$worktree/$prior_protocol_rel"
  --prior-result "$worktree/$prior_package/aggregate_result.json"
  --prior-verification "$worktree/$prior_package/independent_verification.json"
  --prior-package-manifest "$worktree/$prior_package/SHA256SUMS"
  --prior-independent-source "$worktree/$prior_verifier_rel"
  --qualification-protocol "$worktree/$qualification_protocol_rel"
  --qualification-result "$worktree/$qualification_package/formal_summary.json"
  --qualification-verification "$worktree/$qualification_package/verification.json"
  --qualification-package-manifest "$worktree/$qualification_package/SHA256SUMS"
  --independent-graph-qualification-source "$worktree/$qualification_verifier_rel"
  --independent-acquisition-engine "$worktree/$acquisition_verifier_rel"
  --v11-pairs "$worktree/$v11_rel"
  --v11-lineage "$worktree/$lineage_rel"
  --senior-quarantine-protocol "$worktree/$senior_protocol_rel"
  --senior-quarantine-result "$worktree/$senior_package/formal_summary.json"
  --senior-quarantine-verification "$worktree/$senior_package/verification.json"
  --senior-quarantine-manifest "$worktree/$senior_package/MANIFEST.sha256"
  --senior-security-receipt "$cards_root/security_scan.json"
  --senior-cards "$cards_root/cards.safe.json"
  --senior-run-split "$data_root/runsplit_holdruns.json"
  --senior-decision "$data_root/decision.jsonl"
)

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/producer_a.strace" \
  "$python_bin" -m phase1.falsify_historical_run_split_breadth_pareto \
  "${producer_common[@]}" --output "$root/producer_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/producer_b.strace" \
  "$python_bin" -m phase1.falsify_historical_run_split_breadth_pareto \
  "${producer_common[@]}" --output "$root/producer_b.json"
cmp "$root/producer_a.json" "$root/producer_b.json"
readonly result_sha=$(sha256sum "$root/producer_a.json" | awk '{print $1}')

verifier_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --prior-protocol "$worktree/$prior_protocol_rel"
  --prior-result "$worktree/$prior_package/aggregate_result.json"
  --prior-verification "$worktree/$prior_package/independent_verification.json"
  --prior-package-manifest "$worktree/$prior_package/SHA256SUMS"
  --prior-producer-source "$worktree/$prior_producer_rel"
  --qualification-protocol "$worktree/$qualification_protocol_rel"
  --qualification-result "$worktree/$qualification_package/formal_summary.json"
  --qualification-verification "$worktree/$qualification_package/verification.json"
  --qualification-package-manifest "$worktree/$qualification_package/SHA256SUMS"
  --producer-graph-qualification-source "$worktree/$qualification_producer_rel"
  --producer-acquisition-engine "$worktree/$acquisition_producer_rel"
  --v11-pairs "$worktree/$v11_rel"
  --v11-lineage "$worktree/$lineage_rel"
  --senior-quarantine-protocol "$worktree/$senior_protocol_rel"
  --senior-quarantine-result "$worktree/$senior_package/formal_summary.json"
  --senior-quarantine-verification "$worktree/$senior_package/verification.json"
  --senior-quarantine-manifest "$worktree/$senior_package/MANIFEST.sha256"
  --senior-security-receipt "$cards_root/security_scan.json"
  --senior-cards "$cards_root/cards.safe.json"
  --senior-run-split "$data_root/runsplit_holdruns.json"
  --senior-decision "$data_root/decision.jsonl"
  --result "$root/producer_a.json"
  --result-sha256 "$result_sha"
)

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/verifier_a.strace" \
  "$python_bin" -m phase1.verify_historical_run_split_breadth_pareto \
  "${verifier_common[@]}" --output "$root/verifier_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/verifier_b.strace" \
  "$python_bin" -m phase1.verify_historical_run_split_breadth_pareto \
  "${verifier_common[@]}" --output "$root/verifier_b.json"
cmp "$root/verifier_a.json" "$root/verifier_b.json"

"$python_bin" - "$root/producer_a.json" "$root/verifier_a.json" <<'PY'
import json
import pathlib
import sys

producer = json.loads(pathlib.Path(sys.argv[1]).read_text())
verifier = json.loads(pathlib.Path(sys.argv[2]).read_text())
allowed = {
    "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_INTEGRITY_FAIL",
    "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_LIMITED_SUPPORT",
    "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_DOES_NOT_SURVIVE",
    "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_FALSIFICATION_SURVIVES",
}
assert producer["classification"] in allowed
assert producer["status"] == "COMPLETE"
assert producer["full_graph_counts"] == {
    "pairs": 539, "endpoints": 1036, "parents": 505, "physical_runs": 190, "tasks": 36
}
assert verifier["status"] == "INDEPENDENT_RECONSTRUCTION_EXACT"
assert verifier["classification"] == producer["classification"]
assert verifier["all_aggregate_fields_equal"] is True
assert verifier["producer_imported"] is False
assert set(producer["split_profiles"]) == {"fold0", "fold1"}
zero_overlap = {"pairs": 0, "endpoints": 0, "parents": 0, "physical_runs": 0}
if producer["classification"] == "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_INTEGRITY_FAIL":
    assert not all(producer["integrity_gates"].values())
    assert producer["acquisition_computed"] is False
elif producer["classification"] == "POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_LIMITED_SUPPORT":
    assert all(producer["integrity_gates"].values())
    assert producer["cross_fold_overlap"] == zero_overlap
    assert not all(all(gates.values()) for gates in producer["support_gates"].values())
    assert producer["acquisition_computed"] is False
else:
    assert all(producer["integrity_gates"].values())
    assert producer["cross_fold_overlap"] == zero_overlap
    assert all(all(gates.values()) for gates in producer["support_gates"].values())
    assert producer["acquisition_computed"] is True
if producer["acquisition_computed"]:
    assert set(producer["methods_by_fold"]) == {"fold0", "fold1"}
    assert set(producer["gates_by_fold"]) == {"fold0", "fold1"}
else:
    assert producer["methods_by_fold"] == producer["gates_by_fold"] == {}
assert producer["scope"]["post_readout_falsification_only"] is True
assert producer["scope"]["external_confirmation"] is False
assert producer["scope"]["aggregate_only"] is True
assert producer["scope"]["identities_emitted"] is False
assert producer["scope"]["pair_orientation_gap_grade_code_prediction_runtime_used"] is False
assert producer["scope"]["senior_test_rows_used"] is False
assert producer["scope"]["prospective_first960_target300_target522_values_read"] is False
assert producer["scope"]["gpu_api_model_fit_base_update"] == "0/0/0/0"
PY

if grep -Ehi '/external/senior_data|prospective_decision_v1|first[-_]?960|target[-_]?(300|522)|/\.env([" ]|$)|label_vault|outcome_files|prediction[^/]*\.(json|jsonl|csv)' "$root"/*.strace* >"$root/forbidden_opens.txt"; then
  exit 87
fi
if grep -Eh 'connect\(|sendto\(|socket\(' "$root"/*.strace* >"$root/network_calls.txt"; then
  exit 88
fi

git -C "$repo" diff-tree --no-commit-id --name-only -r -z "$control_commit" >"$root/changed_files.zlist"
if tr '\0' '\n' <"$root/changed_files.zlist" | grep -Ei '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' >"$root/credential_filename_hits.txt"; then
  exit 89
fi
readonly credential_value_pattern='(^|[^[:alpha:]])sk-(or-v1-|ws-)?[A-Za-z0-9._-]{20,}|(api[_ -]?key|token|secret)[[:space:]]*[:=][[:space:]]*[^][[:space:]]{20,}'
if printf '%s\n' 'transition-task-snapshot-chain' | grep -E -i -q "$credential_value_pattern"; then
  exit 91
fi
synthetic_secret=$(printf 's%s%024d' 'k-' 0)
if ! printf '%s\n' "$synthetic_secret" | grep -E -i -q "$credential_value_pattern"; then
  exit 92
fi
unset synthetic_secret
: >"$root/credential_blob_hits.txt"
while IFS= read -r -d '' changed; do
  if git -C "$repo" cat-file -e "${control_commit}:${changed}" 2>/dev/null; then
    if git -C "$repo" show "${control_commit}:${changed}" \
      | grep -E -i -n "$credential_value_pattern" \
      >>"$root/credential_blob_hits.txt"; then
      exit 90
    fi
  fi
done <"$root/changed_files.zlist"

printf '%s\n' \
  'postreadout_run_split_falsification=true' \
  'external_confirmation=false' \
  'senior_test_rows_used=false' \
  'pair_orientation_gap_grade_code_prediction_runtime_used=false' \
  'prospective_first960_target300_target522_values_read=false' \
  'raw_senior_archives_opened=false' \
  'identities_emitted=false' \
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
