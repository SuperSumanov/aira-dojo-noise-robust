#!/usr/bin/env bash
set -euo pipefail

source "$HOME/env_setup.sh"
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

COMMIT="${1:?usage: run_operator_support_remote_20260819.sh SOURCE_COMMIT}"
if [[ ! "$COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT_MUST_BE_FULL_SHA1" >&2
  exit 2
fi
REPO="/research/d7/spc/yzyang4/aira-dojo"
WORKTREE="/research/d7/spc/yzyang4/worktrees/operator_support_${COMMIT:0:7}_nosmudge"
STATE_ROOT="/research/d7/spc/yzyang4/prospective_decision_v1"
SNAPSHOT="b3ef1f75b7a111327c3dbad03aee6f03098de01307573ce520f04fa2339314b4"
TRANSACTIONS="$STATE_ROOT/snapshots/$SNAPSHOT/transactions.jsonl"
TRANSACTIONS_SHA="6db342bc711ef4b0445171db796a3efb52b7989524120a17795a1480a7fd1408"
PYTHON="/research/d7/spc/yzyang4/venvs/exp/bin/python"
OUT_A="/research/d7/spc/yzyang4/operator-support-${COMMIT:0:7}-a1"
OUT_B="/research/d7/spc/yzyang4/operator-support-${COMMIT:0:7}-a2"
VERIFY_DIR="/research/d7/spc/yzyang4/operator-support-${COMMIT:0:7}-verification"

for target in "$WORKTREE" "$OUT_A" "$OUT_B" "$VERIFY_DIR"; do
  if [[ -e "$target" ]]; then
    echo "PREEXISTING_TARGET=$target" >&2
    exit 2
  fi
done

git -C "$REPO" fetch fork phase1-value-critic
test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$COMMIT"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT"
test "$(git -C "$WORKTREE" rev-parse HEAD)" = "$COMMIT"
test -z "$(git -C "$WORKTREE" status --porcelain)"
test "$(sha256sum "$TRANSACTIONS" | cut -d' ' -f1)" = "$TRANSACTIONS_SHA"

cd "$WORKTREE"
"$PYTHON" -m pytest phase1/tests -q

for output in "$OUT_A" "$OUT_B"; do
  "$PYTHON" -m phase1.audit_prospective_operator_support \
    --transactions "$TRANSACTIONS" \
    --expect-transactions-sha256 "$TRANSACTIONS_SHA" \
    --expect-transactions 35 \
    --state-root "$STATE_ROOT" \
    --source-commit "$COMMIT" \
    --output "$output"
done

for filename in summary.json parent_support.jsonl sha256_manifest.json; do
  cmp "$OUT_A/$filename" "$OUT_B/$filename"
done

mkdir "$VERIFY_DIR"
"$PYTHON" -m phase1.verify_prospective_operator_support \
  --artifact "$OUT_A" \
  --output "$VERIFY_DIR/a1.json"
"$PYTHON" -m phase1.verify_prospective_operator_support \
  --artifact "$OUT_B" \
  --output "$VERIFY_DIR/a2.json"
cmp "$VERIFY_DIR/a1.json" "$VERIFY_DIR/a2.json"

echo "OPERATOR_SUPPORT_REMOTE_RUN_COMPLETE"
sha256sum "$OUT_A/summary.json" "$OUT_A/parent_support.jsonl" "$OUT_A/sha256_manifest.json" "$VERIFY_DIR/a1.json"
"$PYTHON" -m json.tool "$OUT_A/summary.json"
