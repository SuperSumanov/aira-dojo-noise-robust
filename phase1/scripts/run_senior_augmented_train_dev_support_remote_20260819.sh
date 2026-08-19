#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

COMMIT="${1:?usage: run_senior_augmented_train_dev_support_remote_20260819.sh SOURCE_COMMIT}"
if [[ ! "$COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT_MUST_BE_FULL_SHA1" >&2
  exit 2
fi

REPO="/research/d7/spc/yzyang4/aira-dojo"
WORKTREE="/research/d7/spc/yzyang4/worktrees/augmented_support_${COMMIT:0:7}_nosmudge"
SENIOR_COMMIT="92a9651f2e13a9e43623235b82c07c19721bc2ee"
SENIOR_WORKTREE="/research/d7/spc/yzyang4/worktrees/senior_augmented_${SENIOR_COMMIT:0:7}_nosmudge"
DATA="$SENIOR_WORKTREE/data/augmented_mle_critic"
PYTHON="/research/d7/spc/yzyang4/venvs/exp/bin/python"
OUT_A="/research/d7/spc/yzyang4/senior-augmented-train-dev-support-${COMMIT:0:7}-a1"
OUT_B="/research/d7/spc/yzyang4/senior-augmented-train-dev-support-${COMMIT:0:7}-a2"
VERIFY_DIR="/research/d7/spc/yzyang4/senior-augmented-train-dev-support-${COMMIT:0:7}-verification"

for target in "$WORKTREE" "$OUT_A" "$OUT_B" "$VERIFY_DIR"; do
  if [[ -e "$target" ]]; then
    echo "PREEXISTING_TARGET=$target" >&2
    exit 2
  fi
done

test "$(git -C "$SENIOR_WORKTREE" rev-parse HEAD)" = "$SENIOR_COMMIT"
test -z "$(git -C "$SENIOR_WORKTREE" status --porcelain)"
git -C "$REPO" fetch fork phase1-value-critic
test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$COMMIT"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT"
test "$(git -C "$WORKTREE" rev-parse HEAD)" = "$COMMIT"
test -z "$(git -C "$WORKTREE" status --porcelain)"

cd "$WORKTREE"
"$PYTHON" -m pytest phase1/tests -q

common_args=(
  --cards "$DATA/augmented_cards_current.json"
  --expect-cards-sha256 5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb
  --pairs "$DATA/batch_value_pairs_filtered_runsplit.jsonl"
  --expect-pairs-sha256 c669d672d0a2aeee6da97393e3e832a312295aa5aebd7cd457ff297a27d4d9d2
  --runsplit "$DATA/runsplit_holdruns.json"
  --expect-runsplit-sha256 1323a43b2f52722a66c3fc84fb48e6d8d208c8b8c096eccf4bc7dc14937bb5de
  --source-commit "$COMMIT"
  --senior-source-commit "$SENIOR_COMMIT"
)

"$PYTHON" -m phase1.audit_senior_augmented_train_dev_support "${common_args[@]}" --output "$OUT_A"
"$PYTHON" -m phase1.audit_senior_augmented_train_dev_support "${common_args[@]}" --output "$OUT_B"
for filename in summary.json run_manifest.jsonl pair_structure.jsonl sha256_manifest.json; do
  cmp "$OUT_A/$filename" "$OUT_B/$filename"
done

mkdir "$VERIFY_DIR"
"$PYTHON" -m phase1.verify_senior_augmented_train_dev_support --artifact "$OUT_A" --output "$VERIFY_DIR/a1.json"
"$PYTHON" -m phase1.verify_senior_augmented_train_dev_support --artifact "$OUT_B" --output "$VERIFY_DIR/a2.json"
cmp "$VERIFY_DIR/a1.json" "$VERIFY_DIR/a2.json"

echo "SENIOR_AUGMENTED_TRAIN_DEV_SUPPORT_REMOTE_RUN_COMPLETE"
sha256sum "$OUT_A/summary.json" "$OUT_A/run_manifest.jsonl" "$OUT_A/pair_structure.jsonl" "$OUT_A/sha256_manifest.json" "$VERIFY_DIR/a1.json"
"$PYTHON" -m json.tool "$OUT_A/summary.json"
