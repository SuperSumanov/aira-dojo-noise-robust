#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

CONTROL_COMMIT="${1:?usage: launch_balanced_client_smoke_20260819.sh CONTROL_COMMIT [--submit]}"
MODE="${2:---preflight-only}"
[[ "$CONTROL_COMMIT" =~ ^[0-9a-f]{40}$ ]]
[[ "$MODE" == --preflight-only || "$MODE" == --submit ]]

REPO=/research/d7/spc/yzyang4/aira-dojo
CONTROL_ROOT="/research/d7/spc/yzyang4/worktrees/balanced_client_control_${CONTROL_COMMIT:0:7}_a2_nosmudge"
# The first attempt pinned an older source commit whose Qwen client still resolved
# to qwen-max-latest.  Use one immutable commit for both control and production so
# the three client rows cannot silently differ from the preregistered config.
SOURCE_COMMIT="$CONTROL_COMMIT"
SOURCE_ROOT="$CONTROL_ROOT"
RUN_ROOT="/research/d7/spc/yzyang4/balanced-client-smoke-${CONTROL_COMMIT:0:7}-a2"
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
ENV_FILE=/research/d7/spc/yzyang4/aira-dojo-reproduce/.env

for target in "$CONTROL_ROOT" "$RUN_ROOT"; do
  [[ ! -e "$target" ]] || { echo "PREEXISTING_TARGET=$target" >&2; exit 2; }
done
git -C "$REPO" fetch fork phase1-value-critic
test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$CONTROL_COMMIT"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$CONTROL_ROOT" "$CONTROL_COMMIT"
test -z "$(git -C "$CONTROL_ROOT" status --porcelain --untracked-files=all)"

test "$(git -C "$SOURCE_ROOT" rev-parse HEAD)" = "$SOURCE_COMMIT"
test -z "$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=all)"
test -f "$ENV_FILE"
mkdir -p "$RUN_ROOT/outputs"
cp "$CONTROL_ROOT/phase1/balanced_client_smoke_manifest_20260819.json" "$RUN_ROOT/manifest.json"
cp "$CONTROL_ROOT/phase1/scripts/balanced_client_smoke_20260819.sbatch" "$RUN_ROOT/worker.sbatch"
printf '%s\n' "$CONTROL_COMMIT" >"$RUN_ROOT/control_commit.txt"
printf '%s\n' "$SOURCE_COMMIT" >"$RUN_ROOT/source_commit.txt"

cd "$CONTROL_ROOT"
"$PYTHON" -m pytest phase1/tests -q
set -a
source "$ENV_FILE"
set +a
"$PYTHON" -m phase1.probe_balanced_client_providers | tee "$RUN_ROOT/provider_probe.log"

test "$(sha256sum "$RUN_ROOT/manifest.json" | awk '{print $1}')" = \
  "$(sha256sum "$CONTROL_ROOT/phase1/balanced_client_smoke_manifest_20260819.json" | awk '{print $1}')"
test "$(sha256sum "$RUN_ROOT/worker.sbatch" | awk '{print $1}')" = \
  "$(sha256sum "$CONTROL_ROOT/phase1/scripts/balanced_client_smoke_20260819.sbatch" | awk '{print $1}')"

echo "PREFLIGHT_01_DIRECTION=balanced future exact-stratum client production smoke"
echo "PREFLIGHT_02_MATRIX=3 clients x 1 task x 1 seed = 3 physical runs"
echo "PREFLIGHT_03_BUDGET=step2 execution_timeout300 run_cap900"
echo "PREFLIGHT_04_RESOURCES=3x1 GPU array; Slurm hard cap 1.5 GPU-hours; API approximately 6-12 calls"
echo "PREFLIGHT_05_CLIENTS=deepseek-v4-flash,qwen3-coder-flash,glm-5"
echo "PREFLIGHT_06_TASK=spooky-author-identification seed=1401"
echo "PREFLIGHT_07_FAIRNESS=only client config differs; task seed solver operator budgets fixed"
echo "PREFLIGHT_08_INTEGRITY=resolved config checks all four operators before each run"
echo "PREFLIGHT_09_SECURITY=remote env sourced only; logger.write_env_vars=false; no key copied"
echo "PREFLIGHT_10_SOURCE_COMMIT=$SOURCE_COMMIT"
echo "PREFLIGHT_11_CONTROL_COMMIT=$CONTROL_COMMIT"
echo "PREFLIGHT_12_FAILURE=nonzero worker rc or missing two-step journal kills pilot expansion"
echo "PREFLIGHT_13_EXPANSION=no 12-run pilot until all three smoke rows independently verify"

export BALANCED_SOURCE_ROOT="$SOURCE_ROOT"
export BALANCED_RUN_ROOT="$RUN_ROOT"
export BALANCED_SOURCE_COMMIT="$SOURCE_COMMIT"
sbatch --test-only --array=0-2%3 "$RUN_ROOT/worker.sbatch"
if [[ "$MODE" == --preflight-only ]]; then
  echo "BALANCED_CLIENT_SMOKE_PREFLIGHT_PASS_NOT_SUBMITTED"
  exit 0
fi
submission="$(sbatch --parsable --array=0-2%3 --export=ALL "$RUN_ROOT/worker.sbatch")"
printf '%s\n' "$submission" >"$RUN_ROOT/submission.txt"
echo "BALANCED_CLIENT_SMOKE_SUBMITTED job=$submission run_root=$RUN_ROOT"
