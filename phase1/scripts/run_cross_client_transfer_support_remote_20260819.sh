#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

COMMIT="${1:?usage: run_cross_client_transfer_support_remote_20260819.sh SOURCE_COMMIT}"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]

REPO=/research/d7/spc/yzyang4/aira-dojo
WORKTREE="/research/d7/spc/yzyang4/worktrees/cross_client_support_${COMMIT:0:7}_nosmudge"
SENIOR_COMMIT=92a9651f2e13a9e43623235b82c07c19721bc2ee
SENIOR_WORKTREE="/research/d7/spc/yzyang4/worktrees/senior_augmented_${SENIOR_COMMIT:0:7}_nosmudge"
DATA="$SENIOR_WORKTREE/data/augmented_mle_critic"
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
OUT_A="/research/d7/spc/yzyang4/cross-client-transfer-support-${COMMIT:0:7}-a1"
OUT_B="/research/d7/spc/yzyang4/cross-client-transfer-support-${COMMIT:0:7}-a2"
VERIFY_A="/research/d7/spc/yzyang4/cross-client-transfer-support-${COMMIT:0:7}-verify-a.json"
VERIFY_B="/research/d7/spc/yzyang4/cross-client-transfer-support-${COMMIT:0:7}-verify-b.json"

for target in "$WORKTREE" "$OUT_A" "$OUT_B" "$VERIFY_A" "$VERIFY_B"; do
  [[ ! -e "$target" ]] || { echo "PREEXISTING_TARGET=$target" >&2; exit 2; }
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
common=(
  --cards "$DATA/augmented_cards_current.json"
  --expect-cards-sha256 5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb
  --pairs "$DATA/batch_value_pairs_filtered_runsplit.jsonl"
  --expect-pairs-sha256 c669d672d0a2aeee6da97393e3e832a312295aa5aebd7cd457ff297a27d4d9d2
)
"$PYTHON" -m phase1.audit_cross_client_transfer_support "${common[@]}" \
  --source-commit "$COMMIT" --senior-source-commit "$SENIOR_COMMIT" --output "$OUT_A"
"$PYTHON" -m phase1.audit_cross_client_transfer_support "${common[@]}" \
  --source-commit "$COMMIT" --senior-source-commit "$SENIOR_COMMIT" --output "$OUT_B"
cmp "$OUT_A/summary.json" "$OUT_B/summary.json"
cmp "$OUT_A/eligible_pool.jsonl" "$OUT_B/eligible_pool.jsonl"
cmp "$OUT_A/sha256_manifest.json" "$OUT_B/sha256_manifest.json"
"$PYTHON" -m phase1.verify_cross_client_transfer_support "${common[@]}" --artifact "$OUT_A" --output "$VERIFY_A"
"$PYTHON" -m phase1.verify_cross_client_transfer_support "${common[@]}" --artifact "$OUT_B" --output "$VERIFY_B"
cmp "$VERIFY_A" "$VERIFY_B"
echo CROSS_CLIENT_TRANSFER_SUPPORT_REMOTE_RUN_COMPLETE
sha256sum "$OUT_A/summary.json" "$OUT_A/eligible_pool.jsonl" "$VERIFY_A"
"$PYTHON" -m json.tool "$OUT_A/summary.json"
