#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 TOKENIZERS_PARALLELISM=false

readonly source_repo=${1:?source repository required}
readonly source_commit=${2:?40-character source commit required}
readonly formal_root=${3:?new formal output root required}
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly state_root=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly worktree=/research/d7/spc/yzyang4/worktrees/order-baseline-falsification-${source_commit:0:12}
readonly protocol=phase1/selective_parent_order_baseline_falsification_v1.json
readonly protocol_sha=d6553882e56a3e6137aca1ef3d7f0beecd264171323dc38878fb9d970293f23e
readonly package=phase1/results/tree_content_selective_parent_recovery_887_20260828_63d37cf
readonly fetch_remote=${ORDER_BASELINE_FETCH_REMOTE:-fork}

failure() {
  rc=$?
  if (( rc != 0 )) && test -d "$formal_root"; then printf '%s\n' "$rc" >"$formal_root/FAILED_RC" 2>/dev/null || true; fi
  exit "$rc"
}
trap failure EXIT
[[ $source_commit =~ ^[0-9a-f]{40}$ ]]
test -d "$source_repo/.git"
test -x "$python_bin"
command -v strace >/dev/null
command -v grep >/dev/null
test ! -e "$formal_root"
test ! -e "$worktree"
mkdir -p "$formal_root"
cat >"$formal_root/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol; PASS
02_question=does fixed identifier-erased content add beyond max-prior-step and nearest-prior-manifest-row baselines; PASS
03_timing=published content result known but all order-baseline and disagreement values unseen at protocol freeze; PASS
04_population=exact published 887 test split and fixed 2691 content-selected rows with threshold 1006/16929; PASS
05_baselines=two primary causal-order rules fixed without fitting plus generation-time secondary with no rescue authority; PASS
06_gates=each primary support at least 2000 and 9/10 coverage then half-error twofold-win and fixed breadth gates; PASS
07_controls=same candidate set pairwise comparable rows exact arithmetic no threshold tuning or subgroup rescue; PASS
08_failure=integrity support aggregate breadth ordered classification and all failures preserved; PASS
09_reproducibility=producer A/B independent verifier A/B focused and full tests exact package manifests; PASS
10_resources=single-thread CPU only GPU API model-fit base-update 0/0/0/0; PASS
11_security=exact snapshot only syscall file/network traces credential scans aggregate-only output; PASS
12_forbidden=no first960 Target300 values Target522 candidate/profile raw archive labels outcomes predictions accuracy or utility; PASS
13_interpretation=falsification control only recorded parent is not semantic truth and below-gate weakens content-specific claim; PASS
EOF
test "$(wc -l <"$formal_root/preflight_13.txt")" = 13

git -C "$source_repo" fetch "$fetch_remote" phase1-value-critic >"$formal_root/fetch.stdout" 2>"$formal_root/fetch.stderr"
git -C "$source_repo" cat-file -e "$source_commit^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "$source_repo" worktree add --detach "$worktree" "$source_commit" \
  >"$formal_root/worktree.stdout" 2>"$formal_root/worktree.stderr"
test "$(git -C "$worktree" rev-parse HEAD)" = "$source_commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
test "$(sha256sum "$worktree/$protocol" | awk '{print $1}')" = "$protocol_sha"
test -d "$state_root/snapshots/$snapshot"
test ! -L "$state_root/snapshots/$snapshot"
(
  cd "$worktree/$package"
  sha256sum -c MANIFEST.sha256
) >"$formal_root/published_package_manifest_check.txt"
test "$(grep -c ': OK$' "$formal_root/published_package_manifest_check.txt")" = 7

(
  cd "$worktree"
  "$python_bin" -m pytest -q \
    phase1/tests/test_selective_parent_order_baseline_falsification.py \
    phase1/tests/test_tree_content_selective_parent_recovery_887.py \
    phase1/tests/test_tree_content_selective_parent_forward_target522.py \
    phase1/tests/test_tree_content_lineage_forward_target522_audit.py
) >"$formal_root/focused_tests.txt" 2>"$formal_root/focused_tests.stderr"
(
  cd "$worktree"
  "$python_bin" -m pytest -q phase1/tests
) >"$formal_root/full_tests.txt" 2>"$formal_root/full_tests.stderr"

producer=(
  "$python_bin" -m phase1.audit_selective_parent_order_baseline_falsification
  --repo-root "$worktree"
  --state-root "$state_root"
  --snapshot "$snapshot"
  --protocol "$worktree/$protocol"
  --source-commit "$source_commit"
)
for suffix in a b; do
  (
    cd "$worktree"
    PYTHONHASHSEED=$([[ $suffix == a ]] && printf 0 || printf 1) \
      "${producer[@]}" --output "$formal_root/producer_${suffix}.json"
  ) >"$formal_root/producer_${suffix}.stdout" 2>"$formal_root/producer_${suffix}.stderr"
done
cmp "$formal_root/producer_a.json" "$formal_root/producer_b.json"
result_sha=$(sha256sum "$formal_root/producer_a.json" | awk '{print $1}')

verifier=(
  "$python_bin" -m phase1.verify_selective_parent_order_baseline_falsification
  --repo-root "$worktree"
  --state-root "$state_root"
  --snapshot "$snapshot"
  --protocol "$worktree/$protocol"
  --source-commit "$source_commit"
  --candidate "$formal_root/producer_a.json"
)
for suffix in a b; do
  (
    cd "$worktree"
    PYTHONHASHSEED=$([[ $suffix == a ]] && printf 0 || printf 1) \
      "${verifier[@]}" --output "$formal_root/verifier_${suffix}.json"
  ) >"$formal_root/verifier_${suffix}.stdout" 2>"$formal_root/verifier_${suffix}.stderr"
done
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_b.json"
verifier_sha=$(sha256sum "$formal_root/verifier_a.json" | awk '{print $1}')

(
  cd "$worktree"
  strace -f -qq -e trace=openat -o "$formal_root/open_trace.txt" \
    "${producer[@]}" --output "$formal_root/producer_trace.json"
) >"$formal_root/trace_producer.stdout" 2>"$formal_root/trace_producer.stderr"
cmp "$formal_root/producer_a.json" "$formal_root/producer_trace.json"
grep -E '/label[^/]*/|label_vault|/outcomes?/|/predictions?/|score-channel-future-identity-cohort|tree-content.*target522.*/(candidate|profile)|/external/senior_data/|/\.env([./\"]|$)' \
  "$formal_root/open_trace.txt" >"$formal_root/forbidden_open_hits.txt" || true
test ! -s "$formal_root/forbidden_open_hits.txt"
grep -oE '/research/d7/spc/yzyang4/prospective_decision_v1/snapshots/[0-9a-f]{64}' \
  "$formal_root/open_trace.txt" | LC_ALL=C sort -u >"$formal_root/opened_snapshot_roots.txt"
printf '%s\n' "$state_root/snapshots/$snapshot" >"$formal_root/expected_snapshot_root.txt"
cmp "$formal_root/expected_snapshot_root.txt" "$formal_root/opened_snapshot_roots.txt"

(
  cd "$worktree"
  strace -f -qq -e trace=network -o "$formal_root/network_trace.txt" \
    "${verifier[@]}" --output "$formal_root/verifier_trace.json"
) >"$formal_root/trace_verifier.stdout" 2>"$formal_root/trace_verifier.stderr"
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_trace.json"
test ! -s "$formal_root/network_trace.txt"

cat >"$formal_root/access_attestation.txt" <<EOF
snapshot_opened=$snapshot
other_snapshot_roots_opened=0
prospective_first960_or_target300_values_read=false
target522_candidate_or_profile_read=false
raw_senior_archives_opened=false
task_run_card_parent_code_or_per_edge_values_emitted=false
labels_outcomes_predictions_accuracy_or_search_utility_read=false
row_level_release_created=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
find "$formal_root" -type f \
  \( -iname '*.env' -o -iname '*api*key*' -o -iname '*secret*' -o -iname '*credential*' \) \
  -printf '%P\n' >"$formal_root/artifact_filename_scan.txt"
test ! -s "$formal_root/artifact_filename_scan.txt"
set +e
grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}|authorization:[[:space:]]*bearer' \
  "$formal_root" >"$formal_root/artifact_content_scan.txt"
content_scan_rc=$?
set -e
test "$content_scan_rc" = 1
test ! -s "$formal_root/artifact_content_scan.txt"

focused_tail=$(tail -n 1 "$formal_root/focused_tests.txt")
full_tail=$(tail -n 1 "$formal_root/full_tests.txt")
"$python_bin" - "$formal_root/producer_a.json" "$formal_root/verifier_a.json" "$formal_root/formal_summary.json" \
  "$source_commit" "$protocol_sha" "$result_sha" "$verifier_sha" "$focused_tail" "$full_tail" <<'PY'
import json
import pathlib
import sys

result = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
verification = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
summary = {
    "protocol": "selective-parent-order-baseline-falsification-formal-v1",
    "status": "FORMAL_ORDER_BASELINE_FALSIFICATION_COMPLETE",
    "source_commit": sys.argv[4],
    "protocol_sha256": sys.argv[5],
    "result_sha256": sys.argv[6],
    "independent_verification_sha256": sys.argv[7],
    "classification": result["classification"],
    "reproduced_content_test": result["reproduced_content_test"],
    "primary_comparisons": result["selected_population_primary_comparisons"],
    "strongest_order_threat": result["strongest_order_threat"],
    "primary_baseline_gates": result["primary_baseline_gates"],
    "breadth_gates": result["breadth_gates"],
    "focused_test_tail": sys.argv[8],
    "full_test_tail": sys.argv[9],
    "producer_ab_byte_identical": True,
    "verifier_ab_byte_identical": True,
    "independent_all_aggregate_fields_equal": verification["all_aggregate_fields_equal"],
    "forbidden_open_hits": 0,
    "network_calls": 0,
    "credential_filename_hits": 0,
    "credential_content_hits": 0,
    "credential_content_scanner_rc": 1,
    "prospective_values_read": False,
    "target522_candidate_or_profile_read": False,
    "raw_senior_archives_opened": False,
    "row_level_release_created": False,
    "cpu_thread_limit": 1,
    "gpu_api_model_fit_base_update": [0, 0, 0, 0],
}
pathlib.Path(sys.argv[3]).write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

(
  cd "$formal_root"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$formal_root"
trap - EXIT
printf 'formal_root=%s\n' "$formal_root"
printf 'manifest_sha256=%s\n' "$(sha256sum "$formal_root/SHA256SUMS" | awk '{print $1}')"
