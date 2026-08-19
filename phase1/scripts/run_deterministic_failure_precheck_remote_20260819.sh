#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

COMMIT="${1:?usage: run_deterministic_failure_precheck_remote_20260819.sh SOURCE_COMMIT}"
if [[ ! "$COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT_MUST_BE_FULL_SHA1" >&2
  exit 2
fi

REPO="/research/d7/spc/yzyang4/aira-dojo"
WORKTREE="/research/d7/spc/yzyang4/worktrees/deterministic_precheck_${COMMIT:0:7}_nosmudge"
PYTHON="/research/d7/spc/yzyang4/venvs/exp/bin/python"
CARDS="/research/d7/spc/yzyang4/aira-dojo/phase1/cards_current_v11.jsonl"
STATUS="/research/d7/spc/yzyang4/source-journal-status-v11-42cb6b1-a2/producer/per_child.jsonl"
TAXONOMY="/research/d7/spc/yzyang4/failure-taxonomy-v1-a70cc68/run1/per_child.jsonl"
PAIR_ROOT="/research/d7/spc/yzyang4/failure-risk-pair-support-v1-526e3ad/inputs"
OUT_A="/research/d7/spc/yzyang4/deterministic-failure-precheck-${COMMIT:0:7}-a1"
OUT_B="/research/d7/spc/yzyang4/deterministic-failure-precheck-${COMMIT:0:7}-a2"
VERIFY_DIR="/research/d7/spc/yzyang4/deterministic-failure-precheck-${COMMIT:0:7}-verification"

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

cd "$WORKTREE"
"$PYTHON" -m pytest phase1/tests -q

common_args=(
  --support-summary "$WORKTREE/phase1/results/failure_risk_pair_support_20260817/summary.json"
  --pair-registry "$WORKTREE/phase1/results/failure_risk_pair_registry_20260817/registry.jsonl"
  --expect-pair-registry-sha256 ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747
  --cards "$CARDS"
  --expect-cards-sha256 6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
  --status-per-child "$STATUS"
  --expect-status-sha256 bfb9870d83c50ef2d06bf2d374fc9f9213f41665f4cebeab7ab31837bcfde0d2
  --taxonomy-per-child "$TAXONOMY"
  --expect-taxonomy-sha256 a5f46021d61d1415d49476728fa988feda5cd9d97e80697099f6af467eca2087
  --pair "$PAIR_ROOT/decision_clean_b0.jsonl"
  --expect-pair-sha256 a04b5b805d0bc59b068cbb4df52bcbf23ea429f1b552022829671483eb6d1909
  --pair "$PAIR_ROOT/decision_clean_b1.jsonl"
  --expect-pair-sha256 c2e38643cf2bb78e207964252af4f665961ab81416a762def04226b07c0d9258
  --pair "$PAIR_ROOT/decision_clean_b2.jsonl"
  --expect-pair-sha256 10cbcc86ea8e5861eea3ad6da183e3dac5579533ee8be9890277be98f5de0903
  --root ours=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo
  --root senior_older=/research/d7/spc/yzyang4/external/senior_runs
  --root senior_0806=/research/d7/spc/yzyang4/external/senior_data/extract_0806
  --root senior_0807=/research/d7/spc/yzyang4/external/senior_data/extract_0807
  --root senior_0808=/research/d7/spc/yzyang4/external/senior_data/extract_0808
  --root senior_0809=/research/d7/spc/yzyang4/external/senior_data/extract_0809
  --root senior_0810=/research/d7/spc/yzyang4/external/senior_data/extract_0810_codex_20260813
  --root senior_0811=/research/d7/spc/yzyang4/external/senior_data/extract_0811_codex_20260813_v2
  --source-commit "$COMMIT"
)

"$PYTHON" -m phase1.deterministic_failure_precheck "${common_args[@]}" --output "$OUT_A"
"$PYTHON" -m phase1.deterministic_failure_precheck "${common_args[@]}" --output "$OUT_B"
for filename in summary.json pair_features.jsonl sha256_manifest.json; do
  cmp "$OUT_A/$filename" "$OUT_B/$filename"
done

mkdir "$VERIFY_DIR"
"$PYTHON" -m phase1.verify_deterministic_failure_precheck --artifact "$OUT_A" --output "$VERIFY_DIR/a1.json"
"$PYTHON" -m phase1.verify_deterministic_failure_precheck --artifact "$OUT_B" --output "$VERIFY_DIR/a2.json"
cmp "$VERIFY_DIR/a1.json" "$VERIFY_DIR/a2.json"

echo "DETERMINISTIC_FAILURE_PRECHECK_REMOTE_RUN_COMPLETE"
sha256sum "$OUT_A/summary.json" "$OUT_A/pair_features.jsonl" "$OUT_A/sha256_manifest.json" "$VERIFY_DIR/a1.json"
"$PYTHON" -m json.tool "$OUT_A/summary.json"
