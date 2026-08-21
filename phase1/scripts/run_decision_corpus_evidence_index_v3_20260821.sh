#!/usr/bin/env bash
set -eo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
    echo "usage: $0 CONTROL_COMMIT" >&2
    exit 2
fi

control_commit=$1
short=${control_commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/decision_corpus_evidence_v3_${short}_nosmudge
result_root=/research/d7/spc/yzyang4/decision-corpus-evidence-index-v3
final=$result_root/${short}-v1
staging=$result_root/.${short}-v1.tmp.$$
python=/research/d7/spc/yzyang4/venvs/exp/bin/python

[[ ! -e $final ]] || { echo "formal result already exists: $final" >&2; exit 3; }
mkdir -p "$result_root" "$staging"

cleanup() {
    rc=$?
    if (( rc != 0 )); then
        echo "$rc" > "$staging/FAILED_RC"
        chmod -R a-w "$staging" 2>/dev/null || true
        echo "formal attempt failed and was preserved at $staging" >&2
    fi
    exit "$rc"
}
trap cleanup EXIT

source /uac/y24/yzyang4/env_setup.sh
set -u
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

git -C "$repo" fetch fork phase1-value-critic > "$staging/fetch.stdout" 2> "$staging/fetch.stderr"
git -C "$repo" cat-file -e "$control_commit^{commit}"
if [[ ! -d $worktree ]]; then
    GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$control_commit" \
        > "$staging/worktree.stdout" 2> "$staging/worktree.stderr"
fi
[[ $(git -C "$worktree" rev-parse HEAD) == "$control_commit" ]] || exit 4
git -C "$worktree" status --short > "$staging/worktree_status_before.txt"
[[ ! -s $staging/worktree_status_before.txt ]] || exit 4

cd "$worktree"
export PYTHONPATH="$worktree${PYTHONPATH:+:$PYTHONPATH}"
source_index=phase1/results/decision_corpus_evidence_index_v2_20260821/index.json
formal_summary=phase1/results/decision_observability_funnel_v1_20260821_1b8a7b9/formal_summary.json
builder=phase1/build_decision_corpus_evidence_index_v3.py
verifier=phase1/verify_decision_corpus_evidence_index_v3.py

printf '%s\n' "$control_commit" > "$staging/control_commit.txt"
"$python" --version > "$staging/python_version.txt" 2>&1
git --version > "$staging/git_version.txt"
sha256sum "$source_index" "$formal_summary" "$builder" "$verifier" \
    phase1/decision_corpus_evidence_index_v3_schema.py \
    > "$staging/control_sha256.txt"
cat > "$staging/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_DIRECTION=Decision Corpus evidence release; no predictor or controller tuning
PREFLIGHT_02_QUESTION=can the verified observability funnel be bound as a seventh non-merged evidence estimand
PREFLIGHT_03_INPUT=frozen v2 index plus remote-manifest-pinned funnel summary and independent verification
PREFLIGHT_04_UNIT=one evidence entry with two JSON artifacts and dotted assertions
PREFLIGHT_05_OUTPUT=v3 index with seven separately bounded estimands
PREFLIGHT_06_GATE=exact source hash, artifact hashes, schema reconstruction, and every JSON assertion
PREFLIGHT_07_INFERENCE=none; deterministic evidence packaging only
PREFLIGHT_08_LEAKAGE=no code outcome orientation prediction prospective vault archive or checkpoint
PREFLIGHT_09_CONTROLS=claim drift, hash drift, artifact pin, and source-order tests
PREFLIGHT_10_REPRO=builder x2, independent verifier x2, full commit and hashes embedded
PREFLIGHT_11_FAILURE=no source reordering, threshold change, boundary deletion, or artifact substitution
PREFLIGHT_12_RESOURCES=single-thread CPU, GPU 0, API 0, base-LLM update 0
PREFLIGHT_13_EXPECTED_WALL=under 30 minutes including complete phase1 regression
EOF

"$python" -m pytest phase1/tests/test_decision_corpus_evidence_index_v3.py -q \
    > "$staging/focused_tests.txt" 2> "$staging/focused_tests.stderr"

"$python" "$builder" --repo-root "$worktree" --source-index "$worktree/$source_index" \
    --out "$staging/index_A.json" > "$staging/builder_A.stdout" 2> "$staging/builder_A.stderr"
"$python" "$builder" --repo-root "$worktree" --source-index "$worktree/$source_index" \
    --out "$staging/index_B.json" > "$staging/builder_B.stdout" 2> "$staging/builder_B.stderr"
cmp "$staging/index_A.json" "$staging/index_B.json"

"$python" "$verifier" --repo-root "$worktree" --index "$staging/index_A.json" \
    --out "$staging/verification_A.json" > "$staging/verifier_A.stdout" 2> "$staging/verifier_A.stderr"
"$python" "$verifier" --repo-root "$worktree" --index "$staging/index_B.json" \
    --out "$staging/verification_B.json" > "$staging/verifier_B.stdout" 2> "$staging/verifier_B.stderr"
cmp "$staging/verification_A.json" "$staging/verification_B.json"

cp "$staging/index_A.json" "$staging/index.json"
cp "$staging/verification_A.json" "$staging/independent_verification.json"
rm "$staging/index_A.json" "$staging/index_B.json" "$staging/verification_A.json" "$staging/verification_B.json"

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
echo "DECISION_CORPUS_EVIDENCE_INDEX_V3_COMPLETE $final"
