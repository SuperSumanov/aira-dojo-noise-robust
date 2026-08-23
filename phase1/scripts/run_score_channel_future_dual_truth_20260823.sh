#!/usr/bin/env bash
set -eo pipefail
umask 077

if [[ $# -ne 0 ]]; then
  echo 'usage: run_score_channel_future_dual_truth_20260823.sh' >&2
  exit 64
fi

commit=0000000000000000000000000000000000000000
if [[ ${commit} == 0000000000000000000000000000000000000000 ]]; then
  echo 'truth runner is not release-bound to an approved scientific commit' >&2
  exit 69
fi
set +u
source /uac/y24/yzyang4/env_setup.sh
set -u
short=${commit:0:7}

base_protocol_sha=54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d
base_producer_sha=7df41993d978ae4942d9d8a5dac7ff0a06ae9564edfba30e2d420c7e4a24aa60
base_verifier_sha=090bcf603aecac3181705206690fe29da7012c20c92d0fe832be65f11503ea4f
raw_protocol_sha=4b13814ad53758d21e7f7b531ede5b9a63fd244c7e305833d0513eb77195c8c0
raw_producer_sha=82f3949a8e534302112ca94953a2ad8ee8f5a48b4aade72389c70b7b587860d3
raw_verifier_sha=380cc288b8d27753032a759c06cb1e6b8b10734121c31ece436bc0fcb0f4df4c
mlebench_commit=507f92e1138bb6e40dac5c6ee7a6758e6424bf97
grade_helpers_sha=7d55512a893699b2e17041f3cd3bd0c2aba955c73f50872b3c69238546b87005

base_repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/future_dual_truth_${short}_nosmudge
state_root=/research/d7/spc/yzyang4/prospective_decision_v1
cohort_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
closure_anchor=${cohort_root}/FIRST_CLOSED_COHORT_ANCHOR.json
result_root=/research/d7/spc/yzyang4/score-channel-future-dual-truth
mlebench_repo=/research/d7/spc/yzyang4/mle-bench
grade_helpers=${mlebench_repo}/mlebench/grade_helpers.py
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

test -x "${python_bin}"
test -d "${base_repo}"
test -d "${state_root}"
test -d "${cohort_root}"
test -d "${mlebench_repo}"
test -f "${grade_helpers}"
test ! -e "${worktree}"
test -f "${closure_anchor}"
test ! -L "${closure_anchor}"
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
mapfile -t anchor_values < <("${clean_python[@]}" - "${closure_anchor}" "${cohort_root}" <<'PY'
import hashlib
import json
import pathlib
import sys
anchor = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2]).resolve()
value = json.loads(anchor.read_text(encoding="utf-8"))
cohort = pathlib.Path(value.get("cohort_dir", ""))
sha = value.get("cohort_summary_sha256")
if (
    value.get("protocol") != "score-channel-future-closure-anchor-v1"
    or value.get("status") != "FUTURE_COHORT_FIRST_CLOSURE_ANCHORED_TRUTH_UNREAD"
    or value.get("identity_selected_before_truth") is not True
    or value.get("label_vault_opened") is not False
    or value.get("score_or_outcome_opened") is not False
    or not cohort.is_absolute()
    or cohort.is_symlink()
    or cohort.resolve().parent.parent != root
    or not isinstance(sha, str)
    or len(sha) != 64
    or any(c not in "0123456789abcdef" for c in sha)
    or hashlib.sha256((cohort / "summary.json").read_bytes()).hexdigest() != sha
):
    raise SystemExit("fixed first-closure anchor contract mismatch")
print(cohort)
print(sha)
print(hashlib.sha256(anchor.read_bytes()).hexdigest())
PY
)
test "${#anchor_values[@]}" -eq 3
cohort_dir=${anchor_values[0]}
expected_cohort_sha=${anchor_values[1]}
closure_anchor_sha=${anchor_values[2]}
test -f "${cohort_dir}/summary.json"
test -f "${cohort_dir}/cohort_runs.jsonl"
test -f "${cohort_dir}/cohort_archives.jsonl"
test ! -L "${cohort_dir}/summary.json"
test ! -L "${cohort_dir}/cohort_runs.jsonl"
test ! -L "${cohort_dir}/cohort_archives.jsonl"
test "$(sha256sum "${cohort_dir}/summary.json" | awk '{print $1}')" = "${expected_cohort_sha}"

# Prediction escrow is a hard predecessor of the first outcome-bearing read.
prediction_root=/research/d7/spc/yzyang4/critic-component-breadth-future/${short}-${expected_cohort_sha:0:12}-v1
test -d "${prediction_root}"
test ! -L "${prediction_root}"
test -f "${prediction_root}/COMPLETE"
test -f "${prediction_root}/SHA256SUMS"
test "$(cat "${prediction_root}/COMPLETE")" = \
  FORMAL_FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE_TRUTH_UNREAD
test "$(cat "${prediction_root}/control_commit.txt")" = "${commit}"
test "$(cat "${prediction_root}/cohort_summary_sha256.txt")" = "${expected_cohort_sha}"
test "$(cat "${prediction_root}/closure_anchor_sha256.txt")" = "${closure_anchor_sha}"
(
  cd "${prediction_root}"
  sha256sum -c SHA256SUMS > /dev/null
)
"${clean_python[@]}" - \
  "${prediction_root}/producer_1/summary.json" \
  "${prediction_root}/verification_1.json" \
  "${expected_cohort_sha}" <<'PY'
import json
import sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
verification = json.load(open(sys.argv[2], encoding="utf-8"))
scope = summary.get("scope") or {}
if (
    summary.get("protocol") != "critic-component-breadth-future-escrow-v1"
    or summary.get("status") != "FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE"
    or (summary.get("inputs") or {}).get("cohort_summary_sha256") != sys.argv[3]
    or scope.get("label_vault_read") is not False
    or scope.get("raw_grade_read") is not False
    or scope.get("y_norm_read") is not False
    or scope.get("outcome_metric_computed") is not False
    or verification.get("status") != "INDEPENDENT_SOURCE_REFIT_PASS"
    or verification.get("cohort_summary_sha256") != sys.argv[3]
    or verification.get("label_vault_read") is not False
):
    raise SystemExit("prediction escrow predecessor contract mismatch")
print("PREDICTION_ESCROW_PREDECESSOR_PASS_TRUTH_STILL_UNREAD")
PY

# This guard is intentionally before checkout tests and every production truth module.
# It reads only the aggregate identity summary and must reject a collecting cohort
# before label_vault.jsonl can be opened.
"${clean_python[@]}" - "${cohort_dir}/summary.json" "${base_protocol_sha}" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
closure = summary.get("closure") or {}
inventory = summary.get("inventory") or {}
blindness = summary.get("blindness") or {}
if (
    summary.get("protocol") != "score-channel-future-identity-cohort-v1"
    or summary.get("status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
    or (summary.get("inputs") or {}).get("protocol_sha256") != sys.argv[2]
    or closure.get("accepted_unique_physical_run_target") != 300
    or closure.get("complete_boundary_archive_included") is not True
    or closure.get("remaining_runs_to_target") != 0
    or not isinstance(inventory.get("selected_physical_runs"), int)
    or inventory["selected_physical_runs"] < 300
    or blindness.get("label_vault_opened") is not False
    or blindness.get("score_or_outcome_opened") is not False
    or blindness.get("truth_support_computed") is not False
    or blindness.get("replay_submission_authorized") is not False
):
    raise SystemExit("CLOSED_COHORT_GUARD_FAIL_BEFORE_TRUTH_OPEN")
print("CLOSED_COHORT_GUARD_PASS_TRUTH_STILL_UNREAD")
PY

test "$(git -C "${mlebench_repo}" rev-parse HEAD)" = "${mlebench_commit}"
test -z "$(git -C "${mlebench_repo}" status --porcelain --untracked-files=no)"
test ! -L "${grade_helpers}"
test "$(sha256sum "${grade_helpers}" | awk '{print $1}')" = "${grade_helpers_sha}"

mkdir -p "${result_root}"
tag=${short}-${expected_cohort_sha:0:12}
final=${result_root}/${tag}
staging=${result_root}/.${tag}.tmp.$$
test ! -e "${final}"
test ! -e "${staging}"
mkdir "${staging}"

failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${staging}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${staging}" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

git -C "${base_repo}" fetch fork phase1-value-critic \
  > "${staging}/fetch.stdout" 2> "${staging}/fetch.stderr"
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" != "${commit}"
git -C "${base_repo}" merge-base --is-ancestor "${commit}" fork/phase1-value-critic
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${worktree}" "${commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/status_before.txt"
test ! -s "${staging}/status_before.txt"

base_protocol=${worktree}/phase1/score_channel_future_identifiability_protocol_v1.json
base_producer=${worktree}/phase1/score_channel_future_truth_support.py
base_verifier=${worktree}/phase1/verify_score_channel_future_truth_support.py
raw_protocol=${worktree}/phase1/score_channel_future_raw_grade_support_protocol_v1.json
raw_producer=${worktree}/phase1/score_channel_future_raw_grade_support.py
raw_verifier=${worktree}/phase1/verify_score_channel_future_raw_grade_support.py
test "$(sha256sum "${base_protocol}" | awk '{print $1}')" = "${base_protocol_sha}"
test "$(sha256sum "${base_producer}" | awk '{print $1}')" = "${base_producer_sha}"
test "$(sha256sum "${base_verifier}" | awk '{print $1}')" = "${base_verifier_sha}"
test "$(sha256sum "${raw_protocol}" | awk '{print $1}')" = "${raw_protocol_sha}"
test "$(sha256sum "${raw_producer}" | awk '{print $1}')" = "${raw_producer_sha}"
test "$(sha256sum "${raw_verifier}" | awk '{print $1}')" = "${raw_verifier_sha}"

(
  cd "${worktree}"
  "${clean_python[@]}" -m pytest -p no:cacheprovider \
    phase1/tests/test_score_channel_future_truth_support.py \
    phase1/tests/test_score_channel_future_raw_grade_support.py \
    phase1/tests/test_score_channel_future_dual_truth_runner_contract.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
  "${clean_python[@]}" -m pytest -p no:cacheprovider phase1/tests -q \
    > "${staging}/phase1_tests.stdout" 2> "${staging}/phase1_tests.stderr"
)

printf '%s\n' "${commit}" > "${staging}/control_commit.txt"
printf '%s\n' "${expected_cohort_sha}" > "${staging}/cohort_summary_sha256.txt"
printf '%s\n' "${cohort_dir}" > "${staging}/cohort_dir.txt"
"${clean_python[@]}" --version > "${staging}/python_version.txt" 2>&1
git --version > "${staging}/git_version.txt"

cat > "${staging}/preflight_matrix.txt" <<EOF
PREFLIGHT_01_DIRECTION=current future score-channel dual truth-support gate only
PREFLIGHT_02_QUESTION=does one outcome-blind closed identity cohort support y_norm and official-five-decimal raw-grade estimands
PREFLIGHT_03_COHORT=${expected_cohort_sha}
PREFLIGHT_04_ORDER=closed identity guard then base producer x2 verifier x2 then raw producer x2 verifier x2
PREFLIGHT_05_SELECTION=raw extension reuses base selected_parents byte exactly and independently reconstructs the frozen SHA lottery
PREFLIGHT_06_THRESHOLDS=both estimands retain their separately frozen four gates; neither may overwrite the other
PREFLIGHT_07_INFERENCE=support and balance census only; no effect, replay, winner, or method claim
PREFLIGHT_08_LEAKAGE=label vault opens only after closed identity guard; raw tar blind code scores and replay outcomes stay closed
PREFLIGHT_09_REPRO=fresh exact commit; producer and verifier replicas; source protocol cohort grader and output hashes bound
PREFLIGHT_10_OUTPUT=aggregate statuses and counts only; no card-level grade y_norm gap winner code stdout or submission
PREFLIGHT_11_RESOURCES=single-thread CPU; GPU=0; API=0; model-fit=0; base-LLM-update=0
PREFLIGHT_12_SECURITY=credential scans and file-open trace audit before immutable promotion
PREFLIGHT_13_STOP=any collection SHA closure selection grid replica verifier security or test mismatch fails closed; replay never auto-launches
EOF

base_common=(
  --protocol "${base_protocol}"
  --expect-protocol-sha256 "${base_protocol_sha}"
  --cohort-dir "${cohort_dir}"
  --expect-cohort-summary-sha256 "${expected_cohort_sha}"
  --state-root "${state_root}"
  --repo "${worktree}"
)
for replica in a b; do
  (
    cd "${worktree}"
    strace -ff -e trace=file -o "${staging}/base_producer_${replica}.strace" \
      "${clean_python[@]}" -m phase1.score_channel_future_truth_support \
        "${base_common[@]}" --out-dir "${staging}/base_truth_${replica}" \
        > "${staging}/base_producer_${replica}.stdout" \
        2> "${staging}/base_producer_${replica}.stderr"
  )
done
diff -r "${staging}/base_truth_a" "${staging}/base_truth_b" \
  > "${staging}/base_producer_reproducibility.diff"

for replica in a b; do
  (
    cd "${worktree}"
    strace -ff -e trace=file -o "${staging}/base_verifier_${replica}.strace" \
      "${clean_python[@]}" -m phase1.verify_score_channel_future_truth_support \
        "${base_common[@]}" --truth-dir "${staging}/base_truth_a" \
        --receipt "${staging}/base_verification_${replica}.json" \
        > "${staging}/base_verifier_${replica}.stdout" \
        2> "${staging}/base_verifier_${replica}.stderr"
  )
done
diff "${staging}/base_verification_a.json" "${staging}/base_verification_b.json" \
  > "${staging}/base_verifier_reproducibility.diff"

base_summary_sha=$(sha256sum "${staging}/base_truth_a/summary.json" | awk '{print $1}')
base_selected_sha=$(sha256sum "${staging}/base_truth_a/selected_parents.jsonl" | awk '{print $1}')
base_verification_sha=$(sha256sum "${staging}/base_verification_a.json" | awk '{print $1}')

raw_common=(
  --protocol "${raw_protocol}"
  --expect-protocol-sha256 "${raw_protocol_sha}"
  --base-protocol "${base_protocol}"
  --expect-base-protocol-sha256 "${base_protocol_sha}"
  --cohort-dir "${cohort_dir}"
  --expect-cohort-summary-sha256 "${expected_cohort_sha}"
  --state-root "${state_root}"
  --base-truth-dir "${staging}/base_truth_a"
  --expect-base-truth-summary-sha256 "${base_summary_sha}"
  --expect-base-selected-sha256 "${base_selected_sha}"
  --base-verification "${staging}/base_verification_a.json"
  --expect-base-verification-sha256 "${base_verification_sha}"
  --mlebench-repo "${mlebench_repo}"
  --grade-helpers "${grade_helpers}"
  --repo "${worktree}"
)
for replica in a b; do
  (
    cd "${worktree}"
    strace -ff -e trace=file -o "${staging}/raw_producer_${replica}.strace" \
      "${clean_python[@]}" -m phase1.score_channel_future_raw_grade_support \
        "${raw_common[@]}" --out-dir "${staging}/raw_truth_${replica}" \
        > "${staging}/raw_producer_${replica}.stdout" \
        2> "${staging}/raw_producer_${replica}.stderr"
  )
done
diff -r "${staging}/raw_truth_a" "${staging}/raw_truth_b" \
  > "${staging}/raw_producer_reproducibility.diff"

for replica in a b; do
  (
    cd "${worktree}"
    strace -ff -e trace=file -o "${staging}/raw_verifier_${replica}.strace" \
      "${clean_python[@]}" -m phase1.verify_score_channel_future_raw_grade_support \
        "${raw_common[@]}" --extension-dir "${staging}/raw_truth_a" \
        --receipt "${staging}/raw_verification_${replica}.json" \
        > "${staging}/raw_verifier_${replica}.stdout" \
        2> "${staging}/raw_verifier_${replica}.stderr"
  )
done
diff "${staging}/raw_verification_a.json" "${staging}/raw_verification_b.json" \
  > "${staging}/raw_verifier_reproducibility.diff"

"${clean_python[@]}" - \
  "${staging}/base_truth_a/summary.json" \
  "${staging}/base_verification_a.json" \
  "${staging}/raw_truth_a/summary.json" \
  "${staging}/raw_verification_a.json" \
  "${expected_cohort_sha}" \
  "${staging}/combined_decision.json" <<'PY'
import hashlib
import json
import sys

base_path, base_receipt_path, raw_path, raw_receipt_path, cohort_sha, output = sys.argv[1:]
base = json.load(open(base_path, encoding="utf-8"))
base_receipt = json.load(open(base_receipt_path, encoding="utf-8"))
raw = json.load(open(raw_path, encoding="utf-8"))
raw_receipt = json.load(open(raw_receipt_path, encoding="utf-8"))
base_allowed = {
    "TRUTH_SUPPORT_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY",
    "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST",
}
raw_allowed = {
    "RAW_GRADE_SUPPORT_ELIGIBLE_SEPARATE_DESIGN_REQUEST_ONLY",
    "RAW_GRADE_SUPPORT_KILL_NO_REPLAY_REQUEST",
}
if (
    base.get("status") not in base_allowed
    or raw.get("status") not in raw_allowed
    or not str(base_receipt.get("status", "")).startswith("PASS_")
    or not str(raw_receipt.get("status", "")).startswith("VERIFIED_")
    or (base.get("decision") or {}).get("replay_submission_authorized") is not False
    or (raw.get("decision") or {}).get("replay_submission_authorized") is not False
    or (raw.get("decision") or {}).get("base_y_norm_decision_unchanged") is not True
):
    raise SystemExit("dual truth decision contract mismatch")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
document = {
    "protocol": "score-channel-future-dual-truth-support-handoff-v1",
    "status": "DUAL_TRUTH_SUPPORT_VERIFIED_REPLAY_UNAUTHORIZED",
    "cohort_summary_sha256": cohort_sha,
    "base_y_norm": {
        "status": base["status"],
        "independent_verification_status": base_receipt["status"],
        "summary_sha256": sha(base_path),
        "verification_sha256": sha(base_receipt_path),
        "counts": base["truth_support"]["counts"],
        "gates": base["truth_support"]["gates"],
    },
    "official_five_decimal_raw_grade": {
        "status": raw["status"],
        "independent_verification_status": raw_receipt["status"],
        "summary_sha256": sha(raw_path),
        "verification_sha256": sha(raw_receipt_path),
        "counts": raw["raw_grade_support"]["counts"],
        "gates": raw["raw_grade_support"]["gates"],
    },
    "base_status_overwritten_or_reversed": False,
    "effect_claim_authorized": False,
    "replay_submission_authorized": False,
    "gpu_jobs_authorized": 0,
    "next_action": "report both statuses; only an eligible estimand may receive a separately frozen replay matrix, power analysis, and user GPU-hour approval request",
}
with open(output, "x", encoding="utf-8", newline="\n") as handle:
    json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    handle.write("\n")
PY

forbidden_open_count=$( {
  grep -hEi \
    'open(at|at2)?\(.*(\.tar\.gz|all_blind_views\.jsonl|eligible_blind_manifest\.jsonl|/scores/|replay[^/]*(outcome|result))' \
    "${staging}"/*.strace* || true
} | wc -l )
printf '%s\n' "${forbidden_open_count}" > "${staging}/forbidden_open_count.txt"
test "${forbidden_open_count}" -eq 0

git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/status_after.txt"
test ! -s "${staging}/status_after.txt"
find "${staging}" -type f -printf '%P\n' | LC_ALL=C sort > "${staging}/file_manifest.txt"
filename_count=$(grep -icE 'env|key|token|secret' "${staging}/file_manifest.txt" || true)
content_count=0
while IFS= read -r -d '' artifact; do
  grep_rc=0
  hits=$(grep -IicE '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{16,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "${artifact}") || grep_rc=$?
  test "${grep_rc}" -eq 0 -o "${grep_rc}" -eq 1
  content_count=$((content_count + hits))
done < <(find "${staging}" -type f -print0)
printf '%s\n' "${filename_count}" > "${staging}/filename_scan_count.txt"
printf '%s\n' "${content_count}" > "${staging}/content_scan_count.txt"
test "${filename_count}" -eq 0
test "${content_count}" -eq 0

date -u +%Y-%m-%dT%H:%M:%SZ > "${staging}/completed_at_utc.txt"
printf 'SCORE_CHANNEL_FUTURE_DUAL_TRUTH_FORMAL_COMPLETE_REPLAY_UNAUTHORIZED\n' > "${staging}/COMPLETE"
(
  cd "${staging}"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
)
mv "${staging}" "${final}"
chmod -R a-w "${final}"
trap - EXIT

printf 'result_dir=%s\n' "${final}"
tail -n 1 "${final}/focused_tests.stdout"
tail -n 1 "${final}/phase1_tests.stdout"
cat "${final}/combined_decision.json"
sha256sum "${final}/SHA256SUMS"
