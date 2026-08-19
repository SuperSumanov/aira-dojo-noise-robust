#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

COMMIT="${1:?usage: run_temporal_prediction_escrow_remote_20260819.sh SOURCE_COMMIT}"
if [[ ! "$COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT_MUST_BE_FULL_SHA1" >&2
  exit 2
fi

REPO="/research/d7/spc/yzyang4/aira-dojo"
WORKTREE="/research/d7/spc/yzyang4/worktrees/temporal_escrow_${COMMIT:0:7}_nosmudge"
INPUT="/research/d7/spc/yzyang4/experiments/temporal_blind_0812_v1_20260814"
SCORER="$WORKTREE/phase1/results/fixed_decision_scorer_v11_20260814"
PYTHON="/research/d7/spc/yzyang4/venvs/exp/bin/python"
OUT_A="/research/d7/spc/yzyang4/temporal-prediction-escrow-${COMMIT:0:7}-a1"
OUT_B="/research/d7/spc/yzyang4/temporal-prediction-escrow-${COMMIT:0:7}-a2"
VERIFY_A="/research/d7/spc/yzyang4/temporal-prediction-escrow-${COMMIT:0:7}-verify-a.json"
VERIFY_B="/research/d7/spc/yzyang4/temporal-prediction-escrow-${COMMIT:0:7}-verify-b.json"
TRACE_A="/research/d7/spc/yzyang4/temporal-prediction-escrow-${COMMIT:0:7}-trace-a.log"

for target in "$WORKTREE" "$OUT_A" "$OUT_B" "$VERIFY_A" "$VERIFY_B" "$TRACE_A"; do
  if [[ -e "$target" ]]; then
    echo "PREEXISTING_TARGET=$target" >&2
    exit 2
  fi
done
command -v strace >/dev/null
git -C "$REPO" fetch fork phase1-value-critic
test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$COMMIT"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT"
test "$(git -C "$WORKTREE" rev-parse HEAD)" = "$COMMIT"
test -z "$(git -C "$WORKTREE" status --porcelain)"

cd "$WORKTREE"
"$PYTHON" -m pytest phase1/tests -q

common=(
  --blind-views "$INPUT/blind_views.jsonl"
  --expect-blind-views-sha256 c0d6d207f39ea8d113a90c73e75c982ca9e77356d061ac8bffd8caa53e201dc9
  --structure "$INPUT/blind_sibling_structure.jsonl"
  --expect-structure-sha256 2c67ab3dae40c34b3eea233ae049afa2462d88e689b737b21421a7a1862c993b
  --bundle "$SCORER/fixed_scorer.npz"
  --expect-bundle-sha256 c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23
)
producer_common=(
  "${common[@]}"
  --freeze-receipt "$SCORER/freeze_receipt.json"
  --expect-receipt-sha256 cfab01a80536a50ef21c47ac269c7ce54a11a3b1f0b6daa5700873cbb02ce178
  --denylist "$SCORER/precutoff_endpoint_denylist.csv"
  --expect-denylist-sha256 2f0cc4f3dc203801c569237716ba82cbc2bde2f854b67eee6efa9452e92447e6
  --repo-root "$WORKTREE"
)

strace -f -e trace=openat -o "$TRACE_A" "$PYTHON" -m phase1.temporal_prediction_escrow \
  "${producer_common[@]}" --output "$OUT_A"
if grep -Fq 'label_vault.jsonl' "$TRACE_A"; then
  echo "LABEL_VAULT_OPEN_DETECTED" >&2
  exit 2
fi
"$PYTHON" -m phase1.temporal_prediction_escrow "${producer_common[@]}" --output "$OUT_B"
for name in endpoint_scores.csv pair_predictions.jsonl summary.json sha256_manifest.json; do
  cmp "$OUT_A/$name" "$OUT_B/$name"
done

"$PYTHON" -m phase1.verify_temporal_prediction_escrow "${common[@]}" --artifact "$OUT_A" --output "$VERIFY_A"
"$PYTHON" -m phase1.verify_temporal_prediction_escrow "${common[@]}" --artifact "$OUT_B" --output "$VERIFY_B"
cmp "$VERIFY_A" "$VERIFY_B"

echo "TEMPORAL_PREDICTION_ESCROW_REMOTE_RUN_COMPLETE"
sha256sum "$OUT_A/summary.json" "$OUT_A/endpoint_scores.csv" "$OUT_A/pair_predictions.jsonl" "$VERIFY_A" "$TRACE_A"
"$PYTHON" -m json.tool "$OUT_A/summary.json"
"$PYTHON" -m json.tool "$VERIFY_A"
