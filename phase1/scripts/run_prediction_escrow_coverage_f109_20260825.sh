#!/usr/bin/env bash
set -Eeo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
    echo "usage: $0 CONTROL_COMMIT" >&2
    exit 2
fi

control_commit=$1
short=${control_commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/prediction_coverage_${short}_nosmudge
result_root=/research/d7/spc/yzyang4/prediction-escrow-coverage-matrix
final=$result_root/${short}-f109-v1
staging=$result_root/.${short}-f109-v1.tmp.$$
python=/research/d7/spc/yzyang4/venvs/exp/bin/python
snapshot_sha=f109ac928ed076f83b651af3c4a98bccd11cf592a3c81da541f34f0d2b11d708
wl_root=/research/d7/spc/yzyang4/wl-graph-escrow-current/5826ef7-f109ac928ed0-v1/artifact
transition_root=/research/d7/spc/yzyang4/transition-future-escrow/7458f09-append/20260824T111032Z_f109ac928ed0/artifact
wl_pairs_sha=cd99277991397884f9fcbaa92b7e30175bf69bdc497687eacb1a388d859a1513
wl_summary_sha=1370533dfc808ea8f2f6891d544c2ccfd460a503c5f535e4b6fe078eb9ba94ff
transition_pairs_sha=498a8aebf79027e96294e6c22fdce87e4007cdaeacfbb969198f55627b9db3fe
transition_summary_sha=da62681ed53835de40a9a3dda583e589e05aef7c5bd1d602cc556b78c851d5cf

[[ ! -e $final ]] || { echo "formal result already exists: $final" >&2; exit 3; }
[[ ! -e $worktree ]] || { echo "worktree already exists: $worktree" >&2; exit 3; }
mkdir -p "$result_root" "$staging"

cleanup() {
    rc=$?
    if (( rc != 0 )); then
        printf '%s\n' "$rc" > "$staging/FAILED_RC"
        chmod -R a-w "$staging" 2>/dev/null || true
        echo "formal attempt failed and was preserved at $staging" >&2
    fi
    exit "$rc"
}
trap cleanup EXIT

source /uac/y24/yzyang4/env_setup.sh
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

git -C "$repo" ls-remote fork refs/heads/phase1-value-critic \
    > "$staging/release_ref.txt" 2> "$staging/release_ref.stderr"
release_head=$(awk 'NR == 1 {print $1}' "$staging/release_ref.txt")
[[ $release_head =~ ^[0-9a-f]{40}$ ]] || exit 4
git -C "$repo" fetch --no-write-fetch-head fork "$release_head" \
    > "$staging/fetch.stdout" 2> "$staging/fetch.stderr"
git -C "$repo" cat-file -e "$control_commit^{commit}"
git -C "$repo" cat-file -e "$release_head^{commit}"
git -C "$repo" merge-base --is-ancestor "$control_commit" "$release_head"
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$control_commit" \
    > "$staging/worktree.stdout" 2> "$staging/worktree.stderr"
[[ $(git -C "$worktree" rev-parse HEAD) == "$control_commit" ]] || exit 4
git -C "$worktree" status --short > "$staging/worktree_status_before.txt"
[[ ! -s $staging/worktree_status_before.txt ]] || exit 4

cd "$worktree"
export PYTHONPATH="$worktree${PYTHONPATH:+:$PYTHONPATH}"
builder=phase1/prediction_escrow_coverage_matrix.py
verifier=phase1/verify_prediction_escrow_coverage_matrix.py
protocol=phase1/prediction_escrow_coverage_protocol_v1.json
test_file=phase1/tests/test_prediction_escrow_coverage_matrix.py

printf '%s\n' "$control_commit" > "$staging/control_commit.txt"
printf '%s\n' "$release_head" > "$staging/release_head.txt"
"$python" --version > "$staging/python_version.txt" 2>&1
git --version > "$staging/git_version.txt"
sha256sum "$builder" "$verifier" "$protocol" "$test_file" > "$staging/control_sha256.txt"
sha256sum \
    "$wl_root/pair_predictions.jsonl" \
    "$wl_root/summary.json" \
    "$transition_root/pairs.jsonl" \
    "$transition_root/summary.json" > "$staging/input_sha256.txt"
grep -Fxq "$wl_pairs_sha  $wl_root/pair_predictions.jsonl" "$staging/input_sha256.txt"
grep -Fxq "$wl_summary_sha  $wl_root/summary.json" "$staging/input_sha256.txt"
grep -Fxq "$transition_pairs_sha  $transition_root/pairs.jsonl" "$staging/input_sha256.txt"
grep -Fxq "$transition_summary_sha  $transition_root/summary.json" "$staging/input_sha256.txt"

cat > "$staging/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_ARTIFACT_KNOB=none; four exact input hashes plus same snapshot are checked from producer receipts
PREFLIGHT_02_CHEAP_PATH=focused synthetic suite precedes any real pair parsing; no GPU or API path exists
PREFLIGHT_03_TEST_DEDUP=canonical unordered task/run/parent/children identity must be unique per escrow
PREFLIGHT_04_DISTRIBUTION=pair/run/task/stratum counts and dominant-task share are reported separately per source
PREFLIGHT_05_EVAL_BALANCE=not applicable; no label, prediction effect, mean accuracy, or inferential estimate is computed
PREFLIGHT_06_MODEL_SAVE=not applicable; seven existing predictions are only checked for structural completeness
PREFLIGHT_07_LEAKAGE=no training/test join; no label/grade/outcome/winner-orientation input is accepted
PREFLIGHT_08_RNG=no sampling, fitting, bootstrap, shuffle, or random state is used
PREFLIGHT_09_SECRET=staged release was scanned; formal artifacts receive filename and content scans
PREFLIGHT_10_WALL=single-thread CPU; focused plus full regression expected under 120 minutes
PREFLIGHT_11_POWER=not an effect experiment; no capacity, training amount, or positive-effect claim is made
PREFLIGHT_12_RC=set -Eeuo pipefail and trap preserve the first failed formal attempt with FAILED_RC
PREFLIGHT_13_GROWTH=f109 and all input hashes are immutable; source-set differences are reported rather than sampled away
EOF

cat > "$staging/exact_command.txt" <<EOF
$python $builder --wl-pairs $wl_root/pair_predictions.jsonl --expect-wl-pairs-sha256 $wl_pairs_sha --wl-summary $wl_root/summary.json --expect-wl-summary-sha256 $wl_summary_sha --transition-pairs $transition_root/pairs.jsonl --expect-transition-pairs-sha256 $transition_pairs_sha --transition-summary $transition_root/summary.json --expect-transition-summary-sha256 $transition_summary_sha --expect-snapshot-sha256 $snapshot_sha --output MATRIX
EOF

"$python" -m pytest "$test_file" -q \
    > "$staging/focused_tests.txt" 2> "$staging/focused_tests.stderr"

for replicate in A B; do
    "$python" "$builder" \
        --wl-pairs "$wl_root/pair_predictions.jsonl" \
        --expect-wl-pairs-sha256 "$wl_pairs_sha" \
        --wl-summary "$wl_root/summary.json" \
        --expect-wl-summary-sha256 "$wl_summary_sha" \
        --transition-pairs "$transition_root/pairs.jsonl" \
        --expect-transition-pairs-sha256 "$transition_pairs_sha" \
        --transition-summary "$transition_root/summary.json" \
        --expect-transition-summary-sha256 "$transition_summary_sha" \
        --expect-snapshot-sha256 "$snapshot_sha" \
        --output "$staging/matrix_${replicate}.json" \
        > "$staging/builder_${replicate}.stdout" \
        2> "$staging/builder_${replicate}.stderr"
done
cmp "$staging/matrix_A.json" "$staging/matrix_B.json"
matrix_sha=$(sha256sum "$staging/matrix_A.json" | cut -d' ' -f1)

for replicate in A B; do
    "$python" "$verifier" \
        --matrix "$staging/matrix_${replicate}.json" \
        --expect-matrix-sha256 "$matrix_sha" \
        --wl-pairs "$wl_root/pair_predictions.jsonl" \
        --expect-wl-pairs-sha256 "$wl_pairs_sha" \
        --transition-pairs "$transition_root/pairs.jsonl" \
        --expect-transition-pairs-sha256 "$transition_pairs_sha" \
        --output "$staging/verification_${replicate}.json" \
        > "$staging/verifier_${replicate}.stdout" \
        2> "$staging/verifier_${replicate}.stderr"
done
cmp "$staging/verification_A.json" "$staging/verification_B.json"
cp "$staging/matrix_A.json" "$staging/matrix.json"
cp "$staging/verification_A.json" "$staging/independent_verification.json"
rm "$staging/matrix_A.json" "$staging/matrix_B.json" \
    "$staging/verification_A.json" "$staging/verification_B.json"

"$python" -m pytest phase1/tests -q \
    > "$staging/full_phase1_tests.txt" 2> "$staging/full_phase1_tests.stderr"

git -C "$worktree" status --short > "$staging/worktree_status_after.txt"
[[ ! -s $staging/worktree_status_after.txt ]] || exit 5
find "$staging" -type f -printf '%P\n' | LC_ALL=C sort > "$staging/file_manifest.txt"
name_hits=$(grep -icE 'env|key|token|secret' "$staging/file_manifest.txt" || true)
printf '%s\n' "$name_hits" > "$staging/credential_filename_hits.txt"
content_hits=0
while IFS= read -r -d '' artifact; do
    grep_rc=0
    artifact_hits=$(grep -IicE \
        '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{10,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
        "$artifact") || grep_rc=$?
    [[ $grep_rc == 0 || $grep_rc == 1 ]] || exit 6
    content_hits=$((content_hits + artifact_hits))
done < <(find "$staging" -type f -print0)
printf '%s\n' "$content_hits" > "$staging/credential_content_hits.txt"
[[ $name_hits == 0 && $content_hits == 0 ]] || exit 6

date -u +%Y-%m-%dT%H:%M:%SZ > "$staging/completed_at_utc.txt"
touch "$staging/COMPLETE"
(cd "$staging" && find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z \
    | xargs -0 sha256sum > SHA256SUMS)
chmod -R a-w "$staging"
mv "$staging" "$final"
trap - EXIT
echo "PREDICTION_ESCROW_COVERAGE_COMPLETE $final"
