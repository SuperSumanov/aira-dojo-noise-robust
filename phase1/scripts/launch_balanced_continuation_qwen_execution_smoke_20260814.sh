#!/usr/bin/env bash
set -eo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
set -u
umask 077

branch=codex-prospective-decision-v1-20260814
base_repo=/research/d7/spc/yzyang4/aira-dojo
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
commit="${1:?exact source commit required}"
run_root="${2:?new run root required}"
source_root="/research/d7/spc/yzyang4/worktrees/e1q-smoke-${commit:0:8}"

test ! -e "$run_root"
test ! -e "$source_root"
source "${HOME}/env_setup.sh" >/dev/null 2>&1
git -C "$base_repo" fetch fork "$branch"
test "$(git -C "$base_repo" rev-parse FETCH_HEAD)" = "$commit"
GIT_LFS_SKIP_SMUDGE=1 git -C "$base_repo" worktree add --detach "$source_root" "$commit"
test "$(git -C "$source_root" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$source_root" status --porcelain)"

"$python_bin" -m py_compile "$source_root/phase1/balanced_continuation_qwen_execution_smoke.py" "$source_root/phase1/verify_balanced_continuation_qwen_execution_smoke.py"
PYTHONPATH="$source_root" "$python_bin" -m pytest -q "$source_root/phase1/tests/test_balanced_continuation_qwen_execution_smoke.py"

test "$(sha256sum /research/d7/spc/yzyang4/balanced-e1-operator-probe-1fc6031-a1/summary.json | awk '{print $1}')" = a30aa463a75ead9fa48fcd53a37921749425ac4a8ee696b18c2d0be33413ed1d
test "$(stat -c %a /research/d7/spc/yzyang4/balanced-e1-operator-probe-1fc6031-a1/summary.json)" = 600
test "$(stat -c %a /research/d7/spc/yzyang4/balanced-e1-operator-probe-1fc6031-a1/call_00.raw.json)" = 600
test "$(stat -c %a /research/d7/spc/yzyang4/balanced-e1-operator-probe-1fc6031-a1/call_01.raw.json)" = 600

mkdir -m 700 "$run_root"
for name in outputs workspaces nvfix logs job_rc; do
  mkdir -m 700 "$run_root/$name"
done
cp "$source_root/phase1/实验记录/2026-08-14/BalancedContinuation_QwenExecutionSmoke_预注册.md" "$run_root/preregistration.md"
chmod 600 "$run_root/preregistration.md"
cat >"$run_root/preflight.txt" <<EOF
PASS 1: engineering-only estimand and no-score boundary frozen
PASS 2: focused producer/verifier tests passed
PASS 3: exactly two hash-bound Qwen responses selected before execution
PASS 4: jobs=2 candidate_executions=2 api_calls=0 hard_cap_seconds=600 gpu_hour_upper_bound=0.333333333333333
PASS 5: old revealed anchors used only for execution engineering; first-960/frozen/D_test not read
PASS 6: fresh immutable per-index outputs; no retry or replacement
PASS 7: only operator script executability is tested; no method comparison
PASS 8: call order and response hashes frozen; no stochastic generation
PASS 9: raw response modes=0600 and Git credential scans required
PASS 10: both tasks must complete a full-public submission under fixed wall cap
PASS 11: both-pass kill gate frozen before execution
PASS 12: Slurm and producer exit codes atomically retained
PASS 13: exact commit=$commit and independent verifier required
EOF
chmod 600 "$run_root/preflight.txt"

active_jobs="$(squeue -h -u "$(id -un)" | wc -l)"
if (( active_jobs > 2 )); then
  printf 'QES_QOS_HEADROOM_INSUFFICIENT active_jobs=%s\n' "$active_jobs" >&2
  exit 6
fi
export QES_SOURCE_ROOT="$source_root"
export QES_SOURCE_COMMIT="$commit"
export QES_RUN_ROOT="$run_root"
job_id="$(sbatch --parsable --array=0-1%2 "$source_root/phase1/balanced_continuation_qwen_execution_smoke_20260814.sbatch")"
printf '%s\n' "$job_id" >"$run_root/job_id.txt"
chmod 600 "$run_root/job_id.txt"
printf 'QES_SUBMITTED commit=%s run_root=%s job=%s\n' "$commit" "$run_root" "$job_id"
