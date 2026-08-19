#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

CONTROL_COMMIT="${1:?usage: launch_balanced_client_pilot_20260819.sh CONTROL_COMMIT [--submit]}"
MODE="${2:---preflight-only}"
[[ "$CONTROL_COMMIT" =~ ^[0-9a-f]{40}$ ]]
[[ "$MODE" == --preflight-only || "$MODE" == --submit ]]

REPO=/research/d7/spc/yzyang4/aira-dojo
CONTROL_ROOT="/research/d7/spc/yzyang4/worktrees/balanced_client_pilot_${CONTROL_COMMIT:0:7}_nosmudge"
SOURCE_COMMIT="$CONTROL_COMMIT"
SOURCE_ROOT="$CONTROL_ROOT"
RUN_ROOT="/research/d7/spc/yzyang4/balanced-client-pilot-${CONTROL_COMMIT:0:7}-a1"
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
ENV_FILE=/research/d7/spc/yzyang4/aira-dojo-reproduce/.env

for target in "$CONTROL_ROOT" "$RUN_ROOT"; do
  [[ ! -e "$target" ]] || { echo "PREEXISTING_TARGET=$target" >&2; exit 2; }
done
git -C "$REPO" fetch fork phase1-value-critic
test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$CONTROL_COMMIT"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$CONTROL_ROOT" "$CONTROL_COMMIT"
test -z "$(git -C "$CONTROL_ROOT" status --porcelain --untracked-files=all)"
test -f "$ENV_FILE"
test -d /research/d7/spc/yzyang4/mle-bench/mlebench/competitions/spooky-author-identification
test -d /research/d7/spc/yzyang4/mle-bench/mlebench/competitions/spaceship-titanic
mkdir -p "$RUN_ROOT/outputs"
cp "$CONTROL_ROOT/phase1/balanced_client_pilot_manifest_20260819.json" "$RUN_ROOT/manifest.json"
cp "$CONTROL_ROOT/phase1/scripts/balanced_client_pilot_20260819.sbatch" "$RUN_ROOT/worker.sbatch"
printf '%s\n' "$CONTROL_COMMIT" >"$RUN_ROOT/control_commit.txt"
printf '%s\n' "$SOURCE_COMMIT" >"$RUN_ROOT/source_commit.txt"

cd "$CONTROL_ROOT"
"$PYTHON" -m pytest phase1/tests -q
set -a
source "$ENV_FILE"
set +a
"$PYTHON" -m phase1.probe_balanced_client_providers | tee "$RUN_ROOT/provider_probe.log"

test "$(sha256sum "$RUN_ROOT/manifest.json" | awk '{print $1}')" = \
  "$(sha256sum "$CONTROL_ROOT/phase1/balanced_client_pilot_manifest_20260819.json" | awk '{print $1}')"
test "$(sha256sum "$RUN_ROOT/worker.sbatch" | awk '{print $1}')" = \
  "$(sha256sum "$CONTROL_ROOT/phase1/scripts/balanced_client_pilot_20260819.sbatch" | awk '{print $1}')"

echo "PREFLIGHT_01_DIRECTION=balanced future exact-stratum client production pilot"
echo "PREFLIGHT_02_MATRIX=3 clients x 2 tasks x 2 seeds = 12 physical runs"
echo "PREFLIGHT_03_BUDGET=step4 execution_timeout300 run_cap1800"
echo "PREFLIGHT_04_RESOURCES=4x1 GPU stratum shards x 2h15m; 12 physical runs; Slurm hard cap 9 GPU-hours"
echo "PREFLIGHT_05_API=72 success-path operator calls; extraction-retry protocol cap 144; plus 3 probes"
echo "PREFLIGHT_06_TASKS=spooky-author-identification,spaceship-titanic seeds=1402,1403"
echo "PREFLIGHT_07_FAIRNESS=only client differs within each task-seed exact stratum"
echo "PREFLIGHT_08_INTEGRITY=resolved and final configs verify all four operators"
echo "PREFLIGHT_09_SECURITY=remote env only; logger.write_env_vars=false; no key copied"
echo "PREFLIGHT_10_SOURCE_COMMIT=$SOURCE_COMMIT"
echo "PREFLIGHT_11_CONTROL_COMMIT=$CONTROL_COMMIT"
echo "PREFLIGHT_12_SUPPORT_GATE=all12 structural; each client valid runs>=2; valid nodes>=18; sibling pairs>=6"
echo "PREFLIGHT_13_EFFECT=no client score ranking or winner computation in pilot"

export BALANCED_SOURCE_ROOT="$SOURCE_ROOT"
export BALANCED_RUN_ROOT="$RUN_ROOT"
export BALANCED_SOURCE_COMMIT="$SOURCE_COMMIT"
for pilot_shard in 0 1 2 3; do
  sbatch --test-only --export=ALL,BALANCED_PILOT_SHARD="$pilot_shard" "$RUN_ROOT/worker.sbatch"
done
if [[ "$MODE" == --preflight-only ]]; then
  echo "BALANCED_CLIENT_PILOT_PREFLIGHT_PASS_NOT_SUBMITTED"
  exit 0
fi
: >"$RUN_ROOT/submission.txt"
for pilot_shard in 0 1 2 3; do
  submission="$(sbatch --parsable --export=ALL,BALANCED_PILOT_SHARD="$pilot_shard" "$RUN_ROOT/worker.sbatch")"
  printf '%s\n' "$submission" >>"$RUN_ROOT/submission.txt"
  echo "BALANCED_CLIENT_PILOT_SUBMITTED shard=$pilot_shard job=$submission run_root=$RUN_ROOT"
done
