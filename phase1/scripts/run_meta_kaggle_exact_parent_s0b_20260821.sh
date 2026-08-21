#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u

export BLIS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONHASHSEED=0
export VECLIB_MAXIMUM_THREADS=1
umask 077

COMMIT=${1:?usage: run_meta_kaggle_exact_parent_s0b_20260821.sh SOURCE_COMMIT [OUTPUT]}
SHORT=${COMMIT:0:7}
REPO=/research/d7/spc/yzyang4/aira-dojo
WORKTREE=/research/d7/spc/yzyang4/worktrees/meta_kaggle_exact_parent_s0b_${SHORT}
OUTPUT=${2:-/research/d7/spc/yzyang4/meta-kaggle-exact-parent-s0b/${SHORT}-v1}
INPUT_ROOT=/research/d7/spc/yzyang4/external-audits/meta-kaggle-s0a-20260821
SCRATCH_ROOT=/research/d7/spc/yzyang4/scratch/meta-kaggle-exact-parent-s0b-${SHORT}
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python

PROTOCOL_SHA=451293fdbe13a6563f1c982743d5eaa163f69d0691fdaf4610b5d6c8639a42ad
INPUT_MANIFEST_SHA=21141fe7d390f1d778c6631069c4961b346965410f8754a580763b6afb55b375
KERNELS_SHA=dccccbad40efc018e37b1393d939c20062142a8f28dd19b336d1e186d2983680
VERSIONS_SHA=d8a6a7a4081be92373438b4b9342420e8c8dc775255e42ec54478f6610a98725
LINKS_SHA=abaaee73c7ef464d2c708e82b707d2b3b5ded4938f42bca0a84d3834a0630a35
COMPETITIONS_SHA=a77249dfddc92d1c3d781ac567f876966391c5befb92c81ae52c3e214fbbd0c9

test "$(git -C "$REPO" rev-parse "$COMMIT")" = "$COMMIT"
test ! -e "$WORKTREE"
test ! -e "$OUTPUT"
test ! -e "$SCRATCH_ROOT"
test -f "$INPUT_ROOT/Kernels.csv"
test -f "$INPUT_ROOT/KernelVersions.csv"
test -f "$INPUT_ROOT/KernelVersionCompetitionSources.csv"
test -f "$INPUT_ROOT/Competitions.csv"
mkdir -p "$(dirname "$WORKTREE")" "$(dirname "$OUTPUT")" "$SCRATCH_ROOT"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT"
mkdir "$OUTPUT"

cd "$WORKTREE"
git rev-parse HEAD > "$OUTPUT/source_commit.txt"
git status --porcelain=v1 > "$OUTPUT/source_status.txt"
test ! -s "$OUTPUT/source_status.txt"
sha256sum phase1/meta_kaggle_exact_parent_s0_protocol_v1.json \
  | grep -F "$PROTOCOL_SHA" > "$OUTPUT/protocol_precheck.txt"
sha256sum phase1/meta_kaggle_exact_parent_s0a_input_manifest.json \
  | grep -F "$INPUT_MANIFEST_SHA" > "$OUTPUT/input_manifest_precheck.txt"

cat > "$OUTPUT/preflight_matrix.txt" <<'EOF'
PASS 1: CURRENT_DIRECTION 0CS and the exact-parent protocol are the current dated extension.
PASS 2: S0b reads only four identity/status CSVs and has no outcome-table or notebook-content input.
PASS 3: official daily listing, six CSV hashes, metadata, and required headers are S0a-bound.
PASS 4: units are exact parent version, child Kernel, one pair per parent, and competition.
PASS 5: TraceML join failure and the public missing-join warning are disclosed before this run.
PASS 6: no code, grade, public/private outcome, user text, runtime, or predictor feature is read.
PASS 7: the downloaded outcome table remains unopened beyond its S0a header.
PASS 8: credentials remain in the remote environment and are not printed or copied.
PASS 9: S0b reports exact identity/support counts only and computes no predictor effect.
PASS 10: producer x2, non-importing verifier x2, global exact uniqueness, and SHA manifests are fixed.
PASS 11: CPU-only, single-thread pools, GPU=0, paid API=0, expected 20-90 minutes.
PASS 12: source/input/schema/join/identity/support discrepancies fail closed.
PASS 13: one-shot S0b; S1 must be separately frozen before any outcome data row is opened.
EOF

"$PYTHON" --version > "$OUTPUT/python_version.txt" 2>&1
"$PYTHON" -m pytest -q phase1/tests/test_meta_kaggle_exact_parent_s0b.py \
  > "$OUTPUT/focused_tests.txt" 2>&1
"$PYTHON" -m pytest -q phase1/tests > "$OUTPUT/full_phase1_tests.txt" 2>&1

if grep -Ei 'Submissions\.csv|PublicScore|PrivateScore|SourceKernelVersionId' \
  phase1/meta_kaggle_exact_parent_s0b.py phase1/verify_meta_kaggle_exact_parent_s0b.py \
  > "$OUTPUT/forbidden_source_matches.txt"; then
  exit 1
fi
: > "$OUTPUT/forbidden_source_matches.txt"

COMMON=(
  --repo-root "$WORKTREE"
  --source-commit "$COMMIT"
  --protocol "$WORKTREE/phase1/meta_kaggle_exact_parent_s0_protocol_v1.json"
  --expect-protocol-sha256 "$PROTOCOL_SHA"
  --kernels "$INPUT_ROOT/Kernels.csv"
  --expect-kernels-sha256 "$KERNELS_SHA"
  --kernel-versions "$INPUT_ROOT/KernelVersions.csv"
  --expect-kernel-versions-sha256 "$VERSIONS_SHA"
  --competition-links "$INPUT_ROOT/KernelVersionCompetitionSources.csv"
  --expect-competition-links-sha256 "$LINKS_SHA"
  --competitions "$INPUT_ROOT/Competitions.csv"
  --expect-competitions-sha256 "$COMPETITIONS_SHA"
  --scratch-root "$SCRATCH_ROOT"
)

printf '%q ' "$PYTHON" -m phase1.meta_kaggle_exact_parent_s0b "${COMMON[@]}" --output PRODUCER \
  > "$OUTPUT/producer_command.txt"
printf '\n' >> "$OUTPUT/producer_command.txt"

/usr/bin/time -v -o "$OUTPUT/producer_1.time.txt" \
  strace -ff -e trace=file,network -o "$OUTPUT/producer_1.strace" \
  "$PYTHON" -m phase1.meta_kaggle_exact_parent_s0b "${COMMON[@]}" \
  --output "$OUTPUT/producer_1" > "$OUTPUT/producer_1.stdout.txt" 2> "$OUTPUT/producer_1.stderr.txt"

/usr/bin/time -v -o "$OUTPUT/producer_2.time.txt" \
  "$PYTHON" -m phase1.meta_kaggle_exact_parent_s0b "${COMMON[@]}" \
  --output "$OUTPUT/producer_2" > "$OUTPUT/producer_2.stdout.txt" 2> "$OUTPUT/producer_2.stderr.txt"

diff -ru "$OUTPUT/producer_1" "$OUTPUT/producer_2" > "$OUTPUT/producer_reproducibility.diff"
PRODUCER_MANIFEST_SHA=$(sha256sum "$OUTPUT/producer_1/sha256_manifest.json" | awk '{print $1}')

VERIFY=(
  "${COMMON[@]}"
  --producer-dir "$OUTPUT/producer_1"
  --expect-producer-manifest-sha256 "$PRODUCER_MANIFEST_SHA"
)
printf '%q ' "$PYTHON" -m phase1.verify_meta_kaggle_exact_parent_s0b "${VERIFY[@]}" --output VERIFICATION \
  > "$OUTPUT/verifier_command.txt"
printf '\n' >> "$OUTPUT/verifier_command.txt"

for RUN in 1 2; do
  /usr/bin/time -v -o "$OUTPUT/verifier_${RUN}.time.txt" \
    "$PYTHON" -m phase1.verify_meta_kaggle_exact_parent_s0b "${VERIFY[@]}" \
    --output "$OUTPUT/verification_${RUN}.json" \
    > "$OUTPUT/verifier_${RUN}.stdout.txt" 2> "$OUTPUT/verifier_${RUN}.stderr.txt"
done
diff -u "$OUTPUT/verification_1.json" "$OUTPUT/verification_2.json" \
  > "$OUTPUT/verifier_reproducibility.diff"

FORBIDDEN_PATH_COUNT=$(grep -hEi 'Submissions\.csv|KernelVersionKernelSources\.csv|meta-kaggle-code|\.ipynb' \
  "$OUTPUT"/producer_1.strace* 2>/dev/null | wc -l || true)
NETWORK_CONNECT_COUNT=$(grep -hE 'connect\(.*sa_family=AF_INET(6)?' \
  "$OUTPUT"/producer_1.strace* 2>/dev/null | wc -l || true)
printf '%s\n' "$FORBIDDEN_PATH_COUNT" > "$OUTPUT/forbidden_path_count.txt"
printf '%s\n' "$NETWORK_CONNECT_COUNT" > "$OUTPUT/network_connect_count.txt"
test "$FORBIDDEN_PATH_COUNT" -eq 0
test "$NETWORK_CONNECT_COUNT" -eq 0

if find "$OUTPUT" -type f -printf '%f\n' | grep -iE 'env|key|token|secret' \
  > "$OUTPUT/filename_scan_matches.txt"; then
  exit 1
fi
: > "$OUTPUT/filename_scan_matches.txt"
if grep -RIlE '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{16,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$OUTPUT" > "$OUTPUT/shape_scan_matches.txt"; then
  exit 1
fi
: > "$OUTPUT/shape_scan_matches.txt"

printf '%s\n' 'META_KAGGLE_EXACT_PARENT_S0B_FORMAL_COMPLETE' > "$OUTPUT/COMPLETE"
find "$OUTPUT" -type f ! -name output_manifest.sha256 -print0 \
  | sort -z | xargs -0 sha256sum > "$OUTPUT/output_manifest.sha256"
chmod -R a-w "$OUTPUT"
printf '%s\n' "$OUTPUT"
