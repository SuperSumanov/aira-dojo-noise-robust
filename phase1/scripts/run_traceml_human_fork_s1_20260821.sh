#!/usr/bin/env bash
set -eo pipefail

source /uac/y24/yzyang4/env_setup.sh
set -u

# Keep the complete regression suite and both scientific implementations on the
# same deterministic CPU contract used by prior formal phase1 audits.
export BLIS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONHASHSEED=0
export VECLIB_MAXIMUM_THREADS=1

COMMIT=${1:?usage: run_traceml_human_fork_s1_20260821.sh SOURCE_COMMIT [OUTPUT]}
SHORT=${COMMIT:0:7}
REPO=/research/d7/spc/yzyang4/aira-dojo
WORKTREE=/research/d7/spc/yzyang4/worktrees/traceml_human_fork_s1_${SHORT}_nosmudge
OUTPUT=${2:-/research/d7/spc/yzyang4/external-audits/traceml-human-fork-s1/${SHORT}-v1}
DATASET=/research/d7/spc/yzyang4/external/traceml-61faec615b179f186dbe9c82ee59d17e14817e96
TRAIN=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl
DEV=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
PROTOCOL_SHA=572f51f836c02ffad686e8c79355fd8cfff66a3cbc5a290a89401e4e18354bb2
INPUT_MANIFEST_SHA=e19141d2e5910ef18f8c6fe1392493f34167d70ef7c5b1d39442bfa872cff90f
TRAIN_SHA=0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e
DEV_SHA=3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4

test "$(git -C "$REPO" rev-parse "$COMMIT")" = "$COMMIT"
test ! -e "$WORKTREE"
test ! -e "$OUTPUT"
mkdir -p "$(dirname "$WORKTREE")" "$(dirname "$OUTPUT")"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT"
mkdir "$OUTPUT"

cd "$WORKTREE"
git rev-parse HEAD > "$OUTPUT/source_commit.txt"
git status --porcelain=v1 > "$OUTPUT/source_status.txt"
test ! -s "$OUTPUT/source_status.txt"
"$PYTHON" --version > "$OUTPUT/python_version.txt" 2>&1
"$PYTHON" - <<'PY' > "$OUTPUT/dependency_versions.json"
import json
import numpy
import pyarrow
import scipy
import sklearn
print(json.dumps({
    "numpy": numpy.__version__,
    "pyarrow": pyarrow.__version__,
    "python": __import__("platform").python_version(),
    "scipy": scipy.__version__,
    "sklearn": sklearn.__version__,
}, indent=2, sort_keys=True))
PY

"$PYTHON" -m pytest -q phase1/tests/test_traceml_human_fork_s1_support.py \
    > "$OUTPUT/focused_tests.txt" 2>&1
"$PYTHON" -m pytest -q phase1/tests > "$OUTPUT/full_phase1_tests.txt" 2>&1

COMMON=(
    --repo-root "$WORKTREE"
    --source-commit "$COMMIT"
    --protocol "$WORKTREE/phase1/traceml_human_fork_future_protocol_v1.json"
    --expect-protocol-sha256 "$PROTOCOL_SHA"
    --input-manifest "$WORKTREE/phase1/traceml_human_fork_s0_input_manifest.json"
    --expect-input-manifest-sha256 "$INPUT_MANIFEST_SHA"
    --dataset-root "$DATASET"
    --train-pairs "$TRAIN"
    --expect-train-sha256 "$TRAIN_SHA"
    --dev-pairs "$DEV"
    --expect-dev-sha256 "$DEV_SHA"
)

printf '%q ' "$PYTHON" -m phase1.traceml_human_fork_s1_support "${COMMON[@]}" --output SUMMARY \
    > "$OUTPUT/producer_command.txt"
printf '\n' >> "$OUTPUT/producer_command.txt"

set +e
/usr/bin/time -v -o "$OUTPUT/producer_1.time.txt" \
    strace -ff -e trace=file -o "$OUTPUT/producer_1.strace" \
    "$PYTHON" -m phase1.traceml_human_fork_s1_support "${COMMON[@]}" \
    --output "$OUTPUT/summary_1.json" > "$OUTPUT/producer_1.stdout.txt" 2> "$OUTPUT/producer_1.stderr.txt"
PRODUCER_1_RC=$?
set -e
printf '%s\n' "$PRODUCER_1_RC" > "$OUTPUT/producer_1.rc.txt"
test "$PRODUCER_1_RC" -eq 0

set +e
/usr/bin/time -v -o "$OUTPUT/producer_2.time.txt" \
    "$PYTHON" -m phase1.traceml_human_fork_s1_support "${COMMON[@]}" \
    --output "$OUTPUT/summary_2.json" > "$OUTPUT/producer_2.stdout.txt" 2> "$OUTPUT/producer_2.stderr.txt"
PRODUCER_2_RC=$?
set -e
printf '%s\n' "$PRODUCER_2_RC" > "$OUTPUT/producer_2.rc.txt"
test "$PRODUCER_2_RC" -eq 0
cmp "$OUTPUT/summary_1.json" "$OUTPUT/summary_2.json"
: > "$OUTPUT/producer_reproducibility.diff"

SUMMARY_SHA=$(sha256sum "$OUTPUT/summary_1.json" | awk '{print $1}')
VERIFY=(
    "${COMMON[@]}"
    --producer-summary "$OUTPUT/summary_1.json"
    --expect-producer-summary-sha256 "$SUMMARY_SHA"
)
printf '%q ' "$PYTHON" -m phase1.verify_traceml_human_fork_s1_support "${VERIFY[@]}" --output VERIFICATION \
    > "$OUTPUT/verifier_command.txt"
printf '\n' >> "$OUTPUT/verifier_command.txt"

for RUN in 1 2; do
    set +e
    /usr/bin/time -v -o "$OUTPUT/verifier_${RUN}.time.txt" \
        "$PYTHON" -m phase1.verify_traceml_human_fork_s1_support "${VERIFY[@]}" \
        --output "$OUTPUT/verification_${RUN}.json" \
        > "$OUTPUT/verifier_${RUN}.stdout.txt" 2> "$OUTPUT/verifier_${RUN}.stderr.txt"
    RC=$?
    set -e
    printf '%s\n' "$RC" > "$OUTPUT/verifier_${RUN}.rc.txt"
    test "$RC" -eq 0
done
cmp "$OUTPUT/verification_1.json" "$OUTPUT/verification_2.json"
: > "$OUTPUT/verifier_reproducibility.diff"

FORBIDDEN_COUNT=$(grep -hEi 'trajectories_human|\.ipynb|/\.env([^A-Za-z0-9_]|$)' \
    "$OUTPUT"/producer_1.strace* 2>/dev/null | wc -l || true)
printf '%s\n' "$FORBIDDEN_COUNT" > "$OUTPUT/forbidden_path_count.txt"
test "$FORBIDDEN_COUNT" -eq 0

if grep -RIlE '(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' \
    "$OUTPUT" > "$OUTPUT/credential_scan_matches.txt"; then
    exit 1
fi
: > "$OUTPUT/credential_scan_matches.txt"

printf 'TRACEML_HUMAN_FORK_S1_FORMAL_COMPLETE\n' > "$OUTPUT/COMPLETE"
find "$OUTPUT" -type f ! -name artifact_manifest.sha256 -print0 \
    | sort -z | xargs -0 sha256sum > "$OUTPUT/artifact_manifest.sha256"
chmod -R a-w "$OUTPUT"
printf '%s\n' "$OUTPUT"
