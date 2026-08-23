#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# -ne 0 ]]; then
  echo 'usage: run_critic_component_breadth_future_evaluation_20260824.sh' >&2
  exit 64
fi

# Release-only bindings.  The reviewed version is deliberately inert: a later,
# auditable release commit must bind all six values to already-published objects.
control_commit=0000000000000000000000000000000000000000
first_closed_cohort_anchor=/research/d7/spc/yzyang4/score-channel-future-identity-cohort/FIRST_CLOSED_COHORT_ANCHOR.json
first_closed_cohort_anchor_sha=0000000000000000000000000000000000000000000000000000000000000000
prediction_formal_root=/research/d7/spc/yzyang4/critic-component-breadth-future/UNPUBLISHED_PREDICTION_FORMAL_ROOT
prediction_bundle_sha256sums_sha=0000000000000000000000000000000000000000000000000000000000000000
dual_truth_formal_root=/research/d7/spc/yzyang4/score-channel-future-dual-truth/UNPUBLISHED_DUAL_TRUTH_FORMAL_ROOT
dual_truth_bundle_sha256sums_sha=0000000000000000000000000000000000000000000000000000000000000000
zero_sha=0000000000000000000000000000000000000000000000000000000000000000

if [[ ${control_commit} == 0000000000000000000000000000000000000000 ]] ||
  [[ ${first_closed_cohort_anchor_sha} == "${zero_sha}" ]] ||
  [[ ${prediction_bundle_sha256sums_sha} == "${zero_sha}" ]] ||
  [[ ${dual_truth_bundle_sha256sums_sha} == "${zero_sha}" ]] ||
  [[ ${prediction_formal_root} == *UNPUBLISHED* ]] ||
  [[ ${dual_truth_formal_root} == *UNPUBLISHED* ]]; then
  echo 'evaluation runner is not published: exact commit and predecessor bundles remain inert' >&2
  exit 69
fi

source /uac/y24/yzyang4/env_setup.sh

base_repo=/research/d7/spc/yzyang4/aira-dojo
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
state_root=/research/d7/spc/yzyang4/prospective_decision_v1
cohort_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
result_root=/research/d7/spc/yzyang4/critic-component-breadth-future-evaluation

evaluation_contract_sha=1596c6f2abdfdd8b8880937f41099d81db74151e491175c123e581d9b028fdad
prediction_contract_sha=c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b
evaluator_sha=75149647cc3b82e566cadd33249bd438730c2a70bfb390e51ee21a8fb27a108d
evaluation_verifier_sha=73c3ee9a4488cc377ce4497b5fed91ef1bb9834935a0178ad0b97acc2d28ff8d
base_protocol_sha=54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

test -x "${python_bin}"
test -d "${base_repo}"
test -d "${state_root}"
test -d "${cohort_root}"
test "${first_closed_cohort_anchor}" = "${cohort_root}/FIRST_CLOSED_COHORT_ANCHOR.json"
test -f "${first_closed_cohort_anchor}"
test ! -L "${first_closed_cohort_anchor}"
test "$(sha256sum "${first_closed_cohort_anchor}" | awk '{print $1}')" = \
  "${first_closed_cohort_anchor_sha}"

clean_python=(
  env -i
  HOME="${HOME}"
  PATH="${PATH}"
  LANG=C.UTF-8
  LC_ALL=C.UTF-8
  PYTHONDONTWRITEBYTECODE=1
  PYTHONHASHSEED=0
  OMP_NUM_THREADS=1
  OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1
  NUMEXPR_NUM_THREADS=1
  "${python_bin}"
)

verify_complete_bundle() {
  local bundle=$1
  local expected_manifest_sha=$2
  local expected_complete=$3

  test -d "${bundle}"
  test ! -L "${bundle}"
  test -f "${bundle}/COMPLETE"
  test ! -L "${bundle}/COMPLETE"
  test -f "${bundle}/SHA256SUMS"
  test ! -L "${bundle}/SHA256SUMS"
  test "$(cat "${bundle}/COMPLETE")" = "${expected_complete}"
  test "$(sha256sum "${bundle}/SHA256SUMS" | awk '{print $1}')" = \
    "${expected_manifest_sha}"
  test -z "$(find "${bundle}" -type l -print -quit)"
  (
    cd "${bundle}"
    sha256sum -c --strict SHA256SUMS > /dev/null
  )
  "${clean_python[@]}" - "${bundle}" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
if root.is_symlink() or not root.is_dir():
    raise SystemExit("bundle root is not a regular directory")
links = [path for path in root.rglob("*") if path.is_symlink()]
if links:
    raise SystemExit("bundle contains a symlink")
actual = {
    "./" + path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file() and path.name != "SHA256SUMS"
}
expected = set()
for number, line in enumerate((root / "SHA256SUMS").read_text(encoding="utf-8").splitlines(), 1):
    match = re.fullmatch(r"[0-9a-f]{64} [ *](.+)", line)
    if match is None:
        raise SystemExit(f"malformed SHA256SUMS row {number}")
    name = match.group(1)
    relative = pathlib.PurePosixPath(name)
    if not name.startswith("./") or relative.is_absolute() or ".." in relative.parts:
        raise SystemExit(f"unsafe SHA256SUMS path {number}")
    if name in expected:
        raise SystemExit(f"duplicate SHA256SUMS path {number}")
    expected.add(name)
if actual != expected:
    raise SystemExit("bundle file set differs from SHA256SUMS")
PY
}

mapfile -t anchor_values < <("${clean_python[@]}" - \
  "${first_closed_cohort_anchor}" "${cohort_root}" <<'PY'
import hashlib
import json
import pathlib
import sys

anchor_path = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2]).resolve()
anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
cohort = pathlib.Path(anchor.get("cohort_dir", ""))
summary_sha = anchor.get("cohort_summary_sha256")
if (
    anchor.get("protocol") != "score-channel-future-closure-anchor-v1"
    or anchor.get("status") != "FUTURE_COHORT_FIRST_CLOSURE_ANCHORED_TRUTH_UNREAD"
    or anchor.get("identity_selected_before_truth") is not True
    or anchor.get("label_vault_opened") is not False
    or anchor.get("score_or_outcome_opened") is not False
    or anchor.get("replay_submission_authorized") is not False
    or not cohort.is_absolute()
    or cohort.is_symlink()
    or cohort.resolve().parent.parent != root
    or not isinstance(summary_sha, str)
    or re.fullmatch(r"[0-9a-f]{64}", summary_sha) is None
    or hashlib.sha256((cohort / "summary.json").read_bytes()).hexdigest() != summary_sha
):
    raise SystemExit("fixed first-closure anchor contract mismatch")
print(cohort)
print(summary_sha)
PY
)
test "${#anchor_values[@]}" -eq 2
cohort_dir=${anchor_values[0]}
cohort_summary_sha=${anchor_values[1]}
test -f "${cohort_dir}/summary.json"
test -f "${cohort_dir}/cohort_runs.jsonl"
test -f "${cohort_dir}/cohort_archives.jsonl"
test ! -L "${cohort_dir}/summary.json"
test ! -L "${cohort_dir}/cohort_runs.jsonl"
test ! -L "${cohort_dir}/cohort_archives.jsonl"
test "$(sha256sum "${cohort_dir}/summary.json" | awk '{print $1}')" = \
  "${cohort_summary_sha}"

# Authenticate the complete, outcome-free prediction bundle before reading any
# outcome-bearing dual-truth artifact.
verify_complete_bundle \
  "${prediction_formal_root}" \
  "${prediction_bundle_sha256sums_sha}" \
  FORMAL_FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE_TRUTH_UNREAD
test "$(cat "${prediction_formal_root}/control_commit.txt")" = "${control_commit}"
test "$(cat "${prediction_formal_root}/cohort_summary_sha256.txt")" = "${cohort_summary_sha}"
test "$(cat "${prediction_formal_root}/closure_anchor_sha256.txt")" = \
  "${first_closed_cohort_anchor_sha}"
cmp "${prediction_formal_root}/verification_1.json" \
  "${prediction_formal_root}/verification_2.json"

prediction_dir=${prediction_formal_root}/producer_1
prediction_summary_sha=$(sha256sum "${prediction_dir}/summary.json" | awk '{print $1}')
prediction_manifest_sha=$(sha256sum "${prediction_dir}/artifact_manifest.json" | awk '{print $1}')
prediction_verification_sha=$(sha256sum \
  "${prediction_formal_root}/verification_1.json" | awk '{print $1}')
"${clean_python[@]}" - \
  "${prediction_dir}/summary.json" \
  "${prediction_dir}/artifact_manifest.json" \
  "${prediction_formal_root}/verification_1.json" \
  "${control_commit}" "${cohort_summary_sha}" "${prediction_contract_sha}" <<'PY'
import hashlib
import json
import re
import sys

summary_path, manifest_path, receipt_path, commit, cohort_sha, contract_sha = sys.argv[1:]
summary = json.load(open(summary_path, encoding="utf-8"))
manifest = json.load(open(manifest_path, encoding="utf-8"))
receipt = json.load(open(receipt_path, encoding="utf-8"))
scope = summary.get("scope") or {}
required_false = (
    "accuracy_computed",
    "label_vault_path_accepted",
    "label_vault_read",
    "outcome_metric_computed",
    "raw_grade_read",
    "score_directory_opened",
    "y_norm_read",
)
if (
    summary.get("protocol") != "critic-component-breadth-future-escrow-v1"
    or summary.get("status") != "FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE"
    or summary.get("contract_sha256") != contract_sha
    or summary.get("source_commit") != commit
    or (summary.get("inputs") or {}).get("cohort_summary_sha256") != cohort_sha
    or any(scope.get(key) is not False for key in required_false)
    or scope.get("gpu_jobs") != 0
    or scope.get("api_calls") != 0
    or scope.get("base_llm_updates") != 0
    or manifest.get("protocol") != "critic-component-breadth-future-escrow-v1-artifact-manifest-v1"
    or manifest.get("contract_sha256") != contract_sha
    or receipt.get("status") != "INDEPENDENT_SOURCE_REFIT_PASS"
    or receipt.get("contract_sha256") != contract_sha
    or receipt.get("artifact_manifest_sha256")
       != hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()
    or receipt.get("source_commit") != commit
    or receipt.get("cohort_summary_sha256") != cohort_sha
    or receipt.get("label_vault_read") is not False
    or receipt.get("outcome_metrics_computed") != []
    or any(
        re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(key, ""))) is None
        for key in (
            "producer_source_sha256",
            "verifier_source_sha256",
            "selection_reference_source_sha256",
            "source_selection_contract_sha256",
            "training_cards_sha256",
            "training_pairs_sha256",
        )
    )
):
    raise SystemExit("prediction formal predecessor contract mismatch")
print("PREDICTION_FORMAL_PREDECESSOR_VERIFIED")
PY

short=${control_commit:0:7}
worktree=/research/d7/spc/yzyang4/worktrees/component_breadth_future_evaluation_${short}_nosmudge
result_dir=${result_root}/${short}-${cohort_summary_sha:0:12}-v1
if [[ -e ${worktree} || -L ${worktree} || -e ${result_dir} || -L ${result_dir} ]]; then
  echo 'evaluation worktree or result directory already exists' >&2
  exit 68
fi
mkdir -p "${result_root}"
mkdir "${result_dir}"

failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${result_dir}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${result_dir}" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

git -C "${base_repo}" fetch fork phase1-value-critic \
  > "${result_dir}/fetch.stdout" 2> "${result_dir}/fetch.stderr"
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" != "${control_commit}"
git -C "${base_repo}" merge-base --is-ancestor \
  "${control_commit}" fork/phase1-value-critic
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach \
  "${worktree}" "${control_commit}" \
  > "${result_dir}/worktree.stdout" 2> "${result_dir}/worktree.stderr"
test "$(git -C "${worktree}" rev-parse HEAD)" = "${control_commit}"
git -C "${worktree}" status --porcelain --untracked-files=all \
  > "${result_dir}/status_before.txt"
test ! -s "${result_dir}/status_before.txt"

evaluation_contract=${worktree}/phase1/critic_component_breadth_future_evaluation_v1.json
prediction_contract=${worktree}/phase1/critic_component_breadth_future_escrow_v1.json
evaluator=${worktree}/phase1/evaluate_critic_component_breadth_future_escrow.py
evaluation_verifier=${worktree}/phase1/verify_critic_component_breadth_future_evaluation.py
base_protocol=${worktree}/phase1/score_channel_future_identifiability_protocol_v1.json
prediction_producer_source=${worktree}/phase1/critic_component_breadth_future_escrow.py
prediction_verifier_source=${worktree}/phase1/verify_critic_component_breadth_future_escrow.py
selection_reference_source=${worktree}/phase1/verify_critic_component_breadth_equal_budget.py
source_selection_contract=${worktree}/phase1/critic_component_breadth_equal_budget_v1.json
test "$(sha256sum "${evaluation_contract}" | awk '{print $1}')" = "${evaluation_contract_sha}"
test "$(sha256sum "${prediction_contract}" | awk '{print $1}')" = "${prediction_contract_sha}"
test "$(sha256sum "${evaluator}" | awk '{print $1}')" = "${evaluator_sha}"
test "$(sha256sum "${evaluation_verifier}" | awk '{print $1}')" = \
  "${evaluation_verifier_sha}"
test "$(sha256sum "${base_protocol}" | awk '{print $1}')" = "${base_protocol_sha}"

"${clean_python[@]}" - \
  "${prediction_dir}/summary.json" \
  "${prediction_formal_root}/verification_1.json" \
  "${prediction_producer_source}" "${prediction_verifier_source}" \
  "${selection_reference_source}" "${source_selection_contract}" <<'PY'
import hashlib
import json
import pathlib
import sys

summary_path, receipt_path, producer_path, verifier_path, reference_path, contract_path = sys.argv[1:]
load = lambda path: json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
sha = lambda path: hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
summary = load(summary_path)
receipt = load(receipt_path)
if (
    summary.get("source_sha256") != sha(producer_path)
    or receipt.get("producer_source_sha256") != sha(producer_path)
    or receipt.get("verifier_source_sha256") != sha(verifier_path)
    or receipt.get("selection_reference_source_sha256") != sha(reference_path)
    or receipt.get("source_selection_contract_sha256") != sha(contract_path)
):
    raise SystemExit("prediction source provenance mismatch")
print("PREDICTION_SOURCE_PROVENANCE_VERIFIED")
PY

cat > "${result_dir}/preflight_12.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark; future breadth remains a preregistered supporting hypothesis
PREFLIGHT_02_QUESTION=does frozen broad-support curation beat frozen concentrated support on the official-five-decimal future sibling estimand
PREFLIGHT_03_PREDECESSORS=fixed first-closure anchor plus fixed immutable prediction and dual-truth formal roots
PREFLIGHT_04_ORDER=authenticate prediction before any outcome artifact; authenticate dual truth before evaluator
PREFLIGHT_05_POPULATION=exact dual-truth selected-parent bytes; no outcome-dependent parent pair task or truth reselection
PREFLIGHT_06_TRUTH=official-five-decimal raw grade primary; y_norm log-loss and random are non-rescuing diagnostics
PREFLIGHT_07_AGGREGATION=pair within parent, parent within task, three nuisance seeds, equal-task macro
PREFLIGHT_08_GATES=all four raw support gates precede every primary effect field; insufficient support writes no task effects
PREFLIGHT_09_INFERENCE=frozen 20000-draw task bootstrap, type-7 interval, all seeds and every LOTO direction
PREFLIGHT_10_REPRODUCIBILITY=evaluator twice byte-identical plus independent non-importing verifier twice
PREFLIGHT_11_RESOURCES=single-thread CPU; GPU=0; API=0; new-model-fit=0; base-LLM-update=0
PREFLIGHT_12_INTEGRITY=exact commit and source hashes, syscall audit, full-result credential scan, COMPLETE then final SHA
EOF

git diff-tree --root --no-commit-id --name-only -r "${control_commit}" \
  > "${result_dir}/release_changed_files.txt"
tracked_name_hits=$( {
  grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' \
    "${result_dir}/release_changed_files.txt" || true
} | wc -l )
tracked_content_hits=$( {
  git diff-tree --root --no-commit-id -p -r "${control_commit}" \
    | grep -E \
      '(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
    | grep -vF 'sk-abcdefghijklmnop' || true
} | wc -l )
baseline_tracked_name_hits=$( {
  git ls-tree -r --name-only "${control_commit}" \
    | grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' || true
} | wc -l )
printf '%s\n' "${tracked_name_hits}" > "${result_dir}/scan_tracked_names_count.txt"
printf '%s\n' "${tracked_content_hits}" > "${result_dir}/scan_tracked_content_count.txt"
printf '%s\n' "${baseline_tracked_name_hits}" \
  > "${result_dir}/audit_baseline_broad_name_hits_not_a_release_gate.txt"
test "${tracked_name_hits}" -eq 0
test "${tracked_content_hits}" -eq 0

(
  cd "${worktree}"
  "${clean_python[@]}" -m pytest -p no:cacheprovider -q -rs \
    phase1/tests/test_critic_component_breadth_future_evaluation.py \
    phase1/tests/test_verify_critic_component_breadth_future_evaluation.py \
    phase1/tests/test_critic_component_breadth_future_evaluation_runner_contract.py \
    > "${result_dir}/focused_tests.stdout" \
    2> "${result_dir}/focused_tests.stderr"
  "${clean_python[@]}" -m pytest -p no:cacheprovider -q -rs phase1/tests \
    > "${result_dir}/full_phase1_tests.stdout" \
    2> "${result_dir}/full_phase1_tests.stderr"
)

# The prediction predecessor and source implementation are now authenticated.
# It is legal to authenticate the already-published outcome-bearing dual-truth bundle.
verify_complete_bundle \
  "${dual_truth_formal_root}" \
  "${dual_truth_bundle_sha256sums_sha}" \
  SCORE_CHANNEL_FUTURE_DUAL_TRUTH_FORMAL_COMPLETE_REPLAY_UNAUTHORIZED
test "$(cat "${dual_truth_formal_root}/control_commit.txt")" = "${control_commit}"
test "$(cat "${dual_truth_formal_root}/cohort_summary_sha256.txt")" = \
  "${cohort_summary_sha}"
test "$(cat "${dual_truth_formal_root}/cohort_dir.txt")" = "${cohort_dir}"
diff -r "${dual_truth_formal_root}/base_truth_a" \
  "${dual_truth_formal_root}/base_truth_b" \
  > "${result_dir}/dual_base_reproducibility.diff"
cmp "${dual_truth_formal_root}/base_verification_a.json" \
  "${dual_truth_formal_root}/base_verification_b.json"
diff -r "${dual_truth_formal_root}/raw_truth_a" \
  "${dual_truth_formal_root}/raw_truth_b" \
  > "${result_dir}/dual_raw_reproducibility.diff"
cmp "${dual_truth_formal_root}/raw_verification_a.json" \
  "${dual_truth_formal_root}/raw_verification_b.json"

selected_parents=${dual_truth_formal_root}/base_truth_a/selected_parents.jsonl
selected_parents_sha=$(sha256sum "${selected_parents}" | awk '{print $1}')
"${clean_python[@]}" - \
  "${dual_truth_formal_root}/base_truth_a/summary.json" \
  "${dual_truth_formal_root}/base_verification_a.json" \
  "${dual_truth_formal_root}/raw_truth_a/summary.json" \
  "${dual_truth_formal_root}/raw_verification_a.json" \
  "${dual_truth_formal_root}/combined_decision.json" \
  "${selected_parents}" "${cohort_summary_sha}" "${control_commit}" <<'PY'
import hashlib
import json
import pathlib
import sys

base_path, base_receipt_path, raw_path, raw_receipt_path, combined_path, selected_path, cohort_sha, commit = sys.argv[1:]
load = lambda path: json.load(open(path, encoding="utf-8"))
sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()
base = load(base_path)
base_receipt = load(base_receipt_path)
raw = load(raw_path)
raw_receipt = load(raw_receipt_path)
combined = load(combined_path)
selected_sha = sha(selected_path)
selected_rows = [line for line in pathlib.Path(selected_path).read_text(encoding="utf-8").splitlines() if line]
base_allowed = {
    "TRUTH_SUPPORT_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY": "PASS_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY",
    "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST": "PASS_KILL_NO_REPLAY_REQUEST",
}
raw_allowed = {
    "RAW_GRADE_SUPPORT_ELIGIBLE_SEPARATE_DESIGN_REQUEST_ONLY",
    "RAW_GRADE_SUPPORT_KILL_NO_REPLAY_REQUEST",
}
if (
    base.get("protocol") != "score-channel-future-truth-support-v1"
    or base.get("status") not in base_allowed
    or (base.get("inputs") or {}).get("cohort_summary_sha256") != cohort_sha
    or (base.get("outputs") or {}).get("selected_parents_sha256") != selected_sha
    or (base.get("implementation") or {}).get("source_commit") != commit
    or (base.get("decision") or {}).get("replay_submission_authorized") is not False
    or base_receipt.get("protocol") != "score-channel-future-truth-support-independent-verification-v1"
    or base_receipt.get("status") != base_allowed[base.get("status")]
    or base_receipt.get("cohort_summary_sha256") != cohort_sha
    or base_receipt.get("truth_support_summary_sha256") != sha(base_path)
    or base_receipt.get("selected_parents_sha256") != selected_sha
    or base_receipt.get("selected_parents") != len(selected_rows)
    or base_receipt.get("producer_module_imported") is not False
    or base_receipt.get("replay_submission_authorized") is not False
    or raw.get("protocol") != "score-channel-future-raw-grade-support-v1"
    or raw.get("status") not in raw_allowed
    or (raw.get("inputs") or {}).get("cohort_summary_sha256") != cohort_sha
    or (raw.get("inputs") or {}).get("base_truth_summary_sha256") != sha(base_path)
    or (raw.get("inputs") or {}).get("base_selected_parents_sha256") != selected_sha
    or (raw.get("inputs") or {}).get("base_independent_verification_sha256") != sha(base_receipt_path)
    or (raw.get("selection") or {}).get("selected_parent_rows_reused_byte_exactly") is not True
    or (raw.get("selection") or {}).get("selected_parents_sha256") != selected_sha
    or (raw.get("selection") or {}).get("outcome_dependent_reselection") is not False
    or (raw.get("implementation") or {}).get("source_commit") != commit
    or (raw.get("decision") or {}).get("base_y_norm_decision_unchanged") is not True
    or (raw.get("decision") or {}).get("replay_submission_authorized") is not False
    or raw_receipt.get("protocol") != "score-channel-future-raw-grade-support-independent-verification-v1"
    or raw_receipt.get("status") != "VERIFIED_" + raw.get("status", "")
    or raw_receipt.get("cohort_summary_sha256") != cohort_sha
    or raw_receipt.get("base_truth_summary_sha256") != sha(base_path)
    or raw_receipt.get("base_selected_parents_sha256") != selected_sha
    or raw_receipt.get("base_verification_sha256") != sha(base_receipt_path)
    or raw_receipt.get("extension_summary_sha256") != sha(raw_path)
    or raw_receipt.get("extension_producer_module_imported") is not False
    or raw_receipt.get("replay_submission_authorized") is not False
    or combined.get("protocol") != "score-channel-future-dual-truth-support-handoff-v1"
    or combined.get("status") != "DUAL_TRUTH_SUPPORT_VERIFIED_REPLAY_UNAUTHORIZED"
    or combined.get("cohort_summary_sha256") != cohort_sha
    or (combined.get("base_y_norm") or {}).get("summary_sha256") != sha(base_path)
    or (combined.get("base_y_norm") or {}).get("verification_sha256") != sha(base_receipt_path)
    or (combined.get("official_five_decimal_raw_grade") or {}).get("summary_sha256") != sha(raw_path)
    or (combined.get("official_five_decimal_raw_grade") or {}).get("verification_sha256") != sha(raw_receipt_path)
    or combined.get("base_status_overwritten_or_reversed") is not False
    or combined.get("effect_claim_authorized") is not False
    or combined.get("replay_submission_authorized") is not False
    or combined.get("gpu_jobs_authorized") != 0
):
    raise SystemExit("dual-truth formal predecessor or selected-parent binding mismatch")
print("DUAL_TRUTH_FORMAL_PREDECESSOR_VERIFIED")
PY

prediction_verification_sha=$(sha256sum \
  "${prediction_formal_root}/verification_1.json" | awk '{print $1}')
"${clean_python[@]}" - \
  "${result_dir}/input_binding.json" \
  "${control_commit}" \
  "${first_closed_cohort_anchor}" "${first_closed_cohort_anchor_sha}" \
  "${cohort_dir}" "${cohort_summary_sha}" \
  "${prediction_formal_root}" "${prediction_bundle_sha256sums_sha}" \
  "${prediction_summary_sha}" "${prediction_manifest_sha}" "${prediction_verification_sha}" \
  "${dual_truth_formal_root}" "${dual_truth_bundle_sha256sums_sha}" \
  "${selected_parents}" "${selected_parents_sha}" \
  "${evaluation_contract_sha}" "${evaluator_sha}" "${evaluation_verifier_sha}" <<'PY'
import json
import sys

(
    output, commit, anchor, anchor_sha, cohort, cohort_sha,
    prediction_root, prediction_bundle_sha, prediction_summary_sha,
    prediction_manifest_sha, prediction_verification_sha,
    dual_root, dual_bundle_sha, selected, selected_sha,
    protocol_sha, evaluator_sha, verifier_sha,
) = sys.argv[1:]
document = {
    "protocol": "critic-component-breadth-future-evaluation-input-binding-v1",
    "control_commit": commit,
    "first_closed_cohort_anchor": {"path": anchor, "sha256": anchor_sha},
    "cohort": {"path": cohort, "summary_sha256": cohort_sha},
    "prediction_formal": {
        "root": prediction_root,
        "sha256sums_sha256": prediction_bundle_sha,
        "summary_sha256": prediction_summary_sha,
        "artifact_manifest_sha256": prediction_manifest_sha,
        "independent_verification_sha256": prediction_verification_sha,
    },
    "dual_truth_formal": {
        "root": dual_root,
        "sha256sums_sha256": dual_bundle_sha,
        "selected_parents_path": selected,
        "selected_parents_sha256": selected_sha,
    },
    "evaluation": {
        "protocol_sha256": protocol_sha,
        "evaluator_sha256": evaluator_sha,
        "independent_verifier_sha256": verifier_sha,
    },
    "resources": {"gpu_jobs": 0, "api_calls": 0, "new_model_fits": 0, "base_llm_updates": 0},
}
with open(output, "x", encoding="utf-8", newline="\n") as handle:
    json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    handle.write("\n")
PY

common_args=(
  --protocol "${evaluation_contract}"
  --expect-protocol-sha256 "${evaluation_contract_sha}"
  --prediction-dir "${prediction_dir}"
  --expect-prediction-summary-sha256 "${prediction_summary_sha}"
  --expect-prediction-manifest-sha256 "${prediction_manifest_sha}"
  --base-protocol "${base_protocol}"
  --cohort-dir "${cohort_dir}"
  --expect-cohort-summary-sha256 "${cohort_summary_sha}"
  --state-root "${state_root}"
  --selected-parents "${selected_parents}"
  --expect-selected-parents-sha256 "${selected_parents_sha}"
  --repo-root "${worktree}"
)

mkdir "${result_dir}/traces"
for replica in 1 2; do
  (
    cd "${worktree}"
    strace -ff -tt -yy -e trace=file,network \
      -o "${result_dir}/traces/evaluator_${replica}" \
      "${clean_python[@]}" -m phase1.evaluate_critic_component_breadth_future_escrow \
        "${common_args[@]}" --output "${result_dir}/evaluation_${replica}" \
        > "${result_dir}/evaluator_${replica}.stdout" \
        2> "${result_dir}/evaluator_${replica}.stderr"
  )
done
diff -r "${result_dir}/evaluation_1" "${result_dir}/evaluation_2" \
  > "${result_dir}/evaluator_reproducibility.diff"
chmod -R a-w "${result_dir}/evaluation_1" "${result_dir}/evaluation_2"

evaluation_summary_sha=$(sha256sum \
  "${result_dir}/evaluation_1/summary.json" | awk '{print $1}')
evaluation_manifest_sha=$(sha256sum \
  "${result_dir}/evaluation_1/artifact_manifest.json" | awk '{print $1}')
for replica in 1 2; do
  (
    cd "${worktree}"
    strace -ff -tt -yy -e trace=file,network \
      -o "${result_dir}/traces/verifier_${replica}" \
      "${clean_python[@]}" -m phase1.verify_critic_component_breadth_future_evaluation \
        "${common_args[@]}" \
        --evaluation-dir "${result_dir}/evaluation_1" \
        --expect-evaluation-summary-sha256 "${evaluation_summary_sha}" \
        --expect-evaluation-manifest-sha256 "${evaluation_manifest_sha}" \
        --receipt "${result_dir}/verification_${replica}.json" \
        > "${result_dir}/verifier_${replica}.stdout" \
        2> "${result_dir}/verifier_${replica}.stderr"
  )
done
cmp "${result_dir}/verification_1.json" "${result_dir}/verification_2.json"

"${clean_python[@]}" - \
  "${result_dir}/evaluation_1/summary.json" \
  "${result_dir}/verification_1.json" \
  "${result_dir}/evaluation_handoff_receipt.json" \
  "${evaluation_contract_sha}" "${prediction_contract_sha}" \
  "${prediction_summary_sha}" "${prediction_manifest_sha}" \
  "${cohort_summary_sha}" "${selected_parents_sha}" \
  "${evaluation_summary_sha}" "${evaluation_manifest_sha}" \
  "${control_commit}" "${evaluator_sha}" "${evaluation_verifier_sha}" \
  "${base_protocol_sha}" <<'PY'
import hashlib
import json
import sys

(
    summary_path, verification_path, output, protocol_sha, prediction_contract_sha,
    prediction_summary_sha, prediction_manifest_sha, cohort_sha, selected_sha,
    evaluation_summary_sha, evaluation_manifest_sha, commit, evaluator_sha,
    verifier_sha, base_protocol_sha,
) = sys.argv[1:]
summary = json.load(open(summary_path, encoding="utf-8"))
receipt = json.load(open(verification_path, encoding="utf-8"))
expected_status = "VERIFIED_" + summary.get("status", "")
access = receipt.get("access_attestation") or {}
if (
    summary.get("protocol") != "critic-component-breadth-future-evaluation-output-v1"
    or summary.get("evaluation_protocol_sha256") != protocol_sha
    or summary.get("prediction_contract_sha256") != prediction_contract_sha
    or summary.get("source_commit") != commit
    or summary.get("source_sha256") != evaluator_sha
    or receipt.get("protocol") != "critic-component-breadth-future-evaluation-independent-verification-v1"
    or receipt.get("status") != expected_status
    or receipt.get("evaluation_protocol_sha256") != protocol_sha
    or receipt.get("parent_prediction_contract_sha256") != prediction_contract_sha
    or receipt.get("prediction_summary_sha256") != prediction_summary_sha
    or receipt.get("prediction_manifest_sha256") != prediction_manifest_sha
    or receipt.get("cohort_summary_sha256") != cohort_sha
    or receipt.get("selected_parents_sha256") != selected_sha
    or receipt.get("evaluation_summary_sha256") != evaluation_summary_sha
    or receipt.get("evaluation_manifest_sha256") != evaluation_manifest_sha
    or receipt.get("source_commit") != commit
    or receipt.get("evaluator_source_sha256") != evaluator_sha
    or receipt.get("verifier_source_sha256") != verifier_sha
    or receipt.get("base_protocol_sha256") != base_protocol_sha
    or receipt.get("outcome_evaluator_module_imported") is not False
    or access.get("prediction_authenticated_before_outcome_open") is not True
    or access.get("selected_parents_independently_reconstructed") is not True
    or access.get("raw_card_level_labels_written") is not False
    or access.get("pair_level_truth_orientations_written") is not False
    or access.get("gpu_jobs") != 0
    or access.get("api_calls") != 0
    or access.get("new_model_fits") != 0
    or access.get("base_llm_updates") != 0
):
    raise SystemExit("independent evaluation verification contract mismatch")
handoff = {
    "protocol": "critic-component-breadth-future-evaluation-handoff-v1",
    "status": receipt["status"],
    "evaluation_summary_sha256": evaluation_summary_sha,
    "evaluation_manifest_sha256": evaluation_manifest_sha,
    "independent_verification_sha256": hashlib.sha256(open(verification_path, "rb").read()).hexdigest(),
    "support_gates_all_pass": receipt["support_gates_all_pass"],
    "primary_effect_verified": receipt["primary_effect_verified"],
    "primary_positive": receipt["primary_positive"],
    "replicas": {"evaluator_byte_identical": True, "independent_verifier_byte_identical": True},
    "resources": {"gpu_jobs": 0, "api_calls": 0, "new_model_fits": 0, "base_llm_updates": 0},
}
with open(output, "x", encoding="utf-8", newline="\n") as handle:
    json.dump(handoff, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    handle.write("\n")
PY

forbidden_data_open_count=$( {
  grep -hEi \
    'open(at|at2)?\(.*(\.tar\.gz|all_blind_views|eligible_blind_manifest|/scores/|replay[^/]*(outcome|result))' \
    "${result_dir}"/traces/* || true
} | wc -l )
internet_network_count=$( {
  grep -hE \
    '(socket\(AF_INET6?|connect\(.*(sin_addr|sin6_addr)|send(to|msg)\(.*(sin_addr|sin6_addr))' \
    "${result_dir}"/traces/* || true
} | wc -l )
gpu_open_count=$( {
  grep -hEi '(/dev/nvidia|/dev/dri|libcuda|libnvidia)' \
    "${result_dir}"/traces/* || true
} | wc -l )
label_vault_open_count=$( {
  grep -hEi 'open(at|at2)?\(.*label[_-]?vault' \
    "${result_dir}"/traces/* || true
} | wc -l )
printf '%s\n' "${forbidden_data_open_count}" > \
  "${result_dir}/scan_forbidden_data_open_count.txt"
printf '%s\n' "${internet_network_count}" > \
  "${result_dir}/scan_internet_network_count.txt"
printf '%s\n' "${gpu_open_count}" > "${result_dir}/scan_gpu_open_count.txt"
printf '%s\n' "${label_vault_open_count}" > \
  "${result_dir}/scan_label_vault_open_count.txt"
test "${forbidden_data_open_count}" -eq 0
test "${internet_network_count}" -eq 0
test "${gpu_open_count}" -eq 0
test "${label_vault_open_count}" -gt 0

git -C "${worktree}" status --porcelain --untracked-files=all \
  > "${result_dir}/status_after.txt"
test ! -s "${result_dir}/status_after.txt"
"${clean_python[@]}" -VV > "${result_dir}/python_version.txt" 2>&1
"${clean_python[@]}" -m pip freeze --all > "${result_dir}/pip_freeze.txt"
printf '%s\n' "${control_commit}" > "${result_dir}/control_commit.txt"
printf '%s\n' "${first_closed_cohort_anchor_sha}" > \
  "${result_dir}/first_closed_cohort_anchor_sha256.txt"
printf '%s\n' "${prediction_bundle_sha256sums_sha}" > \
  "${result_dir}/prediction_bundle_sha256sums_sha256.txt"
printf '%s\n' "${dual_truth_bundle_sha256sums_sha}" > \
  "${result_dir}/dual_truth_bundle_sha256sums_sha256.txt"
find "${result_dir}" -type f -printf '%P\n' | LC_ALL=C sort \
  > "${result_dir}/artifact_file_manifest.txt"

"${clean_python[@]}" - "${result_dir}" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
name_pattern = re.compile(r"(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$", re.IGNORECASE)
content_patterns = [
    re.compile(rb"(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{16,}"),
    re.compile(rb"hf_[A-Za-z0-9]{16,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key[ \t]*[:=]", re.IGNORECASE),
    re.compile(rb"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
files = sorted(path for path in root.rglob("*") if path.is_file())
filename_hits = [path.relative_to(root).as_posix() for path in files if name_pattern.search(path.relative_to(root).as_posix())]
content_hits = []
for path in files:
    payload = path.read_bytes()
    if any(pattern.search(payload) for pattern in content_patterns):
        content_hits.append(path.relative_to(root).as_posix())
if filename_hits or content_hits:
    raise SystemExit("credential-shaped material found in evaluation result")
receipt = {
    "protocol": "full-result-credential-shape-scan-v1",
    "files_scanned": len(files),
    "filename_hits": 0,
    "content_hits": 0,
    "all_existing_result_files_scanned": True,
}
payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
if any(pattern.search(payload) for pattern in content_patterns):
    raise SystemExit("credential scan receipt is not clean")
(root / "credential_scan_receipt.json").write_bytes(payload)
PY

date -u +%Y-%m-%dT%H:%M:%SZ > "${result_dir}/completed_at_utc.txt"
printf 'FORMAL_FUTURE_COMPONENT_BREADTH_EVALUATION_COMPLETE\n' \
  > "${result_dir}/COMPLETE"
(
  cd "${result_dir}"
  find . -type f ! -name SHA256SUMS -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum \
    > SHA256SUMS
  sha256sum -c --strict SHA256SUMS > /dev/null
)
chmod -R a-w "${result_dir}"
trap - EXIT

printf 'result_dir=%s\n' "${result_dir}"
cat "${result_dir}/evaluation_handoff_receipt.json"
sha256sum "${result_dir}/SHA256SUMS"
