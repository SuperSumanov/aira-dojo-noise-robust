#!/usr/bin/env bash
set -euo pipefail

export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
main=/research/d7/spc/yzyang4/aira-dojo-reproduce
ops=/research/d7/spc/yzyang4/probe_contract_ab_ops/probe_contract_ab_safety_v2
logs=/research/d7/spc/yzyang4/logs
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
commit=${1:?expected git commit required}
prereg_doc="$repo/phase1/实验记录/2026-08-13/probe_contract_ab_safety_v2预注册.md"
bundle="$repo/phase1/probe_contract_ab_safety_v2/prereg"
launcher="$bundle/preflight_launch_probe_contract_ab_v2_20260813.sh"
generation_sbatch="$bundle/probe_contract_ab_v2_generate_20260813.sbatch"
replay_sbatch="$bundle/probe_contract_ab_v2_replay_20260813.sbatch"
watcher="$bundle/watch_probe_contract_ab_v2_20260813.sh"
hydra="$bundle/hydra_preflight_probe_contract_ab_v2_20260813.sh"
independent="$repo/phase1/verify_probe_contract_ab_v2_independent.py"
container=/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif
expected_container_sha=801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda

test "$commit" = "$(printf '%s' "$commit" | grep -E '^[0-9a-f]{40}$')"
test ! -e "$ops"
mkdir -p "$ops/prereg"
printf '%s\n' "$commit" > "$ops/prereg/expected_commit.txt"
exec > >(tee "$ops/prereg/launch_preflight_20260813.txt") 2>&1

echo 'PREFLIGHT_01_KNOBS_ON_DISK'
test -f "$prereg_doc"
test -f "$repo/phase1/probe_contract_ab_common.py"
test -f "$repo/phase1/validate_probe_contract_ab.py"
test -f "$independent"
grep -q '唯一允许变化.*draft system prompt' "$prereg_doc"

echo 'PREFLIGHT_02_CHEAP_TESTS'
cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"
"$py" -m py_compile \
  phase1/probe_contract_ab_common.py \
  phase1/probe_contract_ab_generation_entry.py \
  phase1/build_probe_contract_ab_manifest.py \
  phase1/extract_probe_contract_ab_manifest.py \
  phase1/validate_probe_contract_ab.py \
  phase1/audit_probe_contract_ab_hydra.py \
  phase1/schema_probe_contract_worker.py \
  phase1/verify_probe_contract_ab_v2_independent.py
"$py" -m pytest -q \
  tests/test_probe_contract_ab_pipeline.py \
  tests/test_schema_probe_repair_topology.py \
  tests/test_schema_probe_repair_pipeline.py
"$py" -m phase1.validate_probe_contract_ab --self-test
"$py" phase1/schema_probe_contract_worker.py --self-test
"$py" phase1/verify_probe_contract_ab_v2_independent.py --self-test

echo 'PREFLIGHT_03_TEST_DEDUP_AND_04_BLOCK_DISTRIBUTION'
"$py" - <<'PY'
from phase1.audit_probe_contract_ab_hydra import PRIOR_INTERVENTION_TASKS
from phase1.probe_contract_ab_common import ARMS, spec_for_version

spec = spec_for_version("v2")
assert spec.seed == 887
assert len(spec.matrix) == 16 and len(spec.tasks) == 8
assert not (set(spec.tasks) & PRIOR_INTERVENTION_TASKS)
assert [row["index"] for row in spec.matrix] == list(range(16))
for task in spec.tasks:
    rows = [row for row in spec.matrix if row["task"] == task]
    assert len(rows) == 2 and {row["arm"] for row in rows} == set(ARMS)
for pair_index in range(8):
    pair = spec.matrix[2 * pair_index : 2 * pair_index + 2]
    assert pair[0]["task"] == pair[1]["task"]
    expected_first = "original" if pair_index % 2 == 0 else "contract"
    assert pair[0]["arm"] == expected_first
print("MATRIX_FREEZE_PASS entries=16 blocks=8 prior_related_overlap=0 seed=887")
PY

echo 'PREFLIGHT_05_PAIRED_EVAL_AND_06_ARTIFACT_RETENTION'
grep -q '逐 task 配对' "$prereg_doc"
grep -q '完整 config、status、export、manifest、snapshot' "$prereg_doc"

echo 'PREFLIGHT_07_LEAKAGE_THREE_WAY'
if grep -n -E 'decision_(clean|frozen)_v?[0-9]*_?b[0-9].*jsonl' \
  phase1/probe_contract_ab_common.py \
  phase1/probe_contract_ab_generation_entry.py \
  phase1/build_probe_contract_ab_manifest.py \
  phase1/extract_probe_contract_ab_manifest.py \
  phase1/validate_probe_contract_ab.py \
  phase1/schema_probe_contract_worker.py; then
  echo FROZEN_DECISION_REFERENCE_FOUND >&2
  exit 1
fi
echo 'LEAKAGE_GATE_PASS no_pair_node_or_code_corpus_input'

echo 'PREFLIGHT_08_RNG_ORDER_FREEZE'
grep -q 'seed=887' "$generation_sbatch"
grep -q 'metadata.seed=887' "$hydra"
grep -q 'Arm order alternates' "$prereg_doc"

echo 'PREFLIGHT_09_REMOTE_CREDENTIAL_AND_BALANCE'
(
  set +u
  source "$HOME/env_setup.sh"
  set -a
  source "$main/.env"
  set +a
  set -u
  test -n "${PRIMARY_KEY_DEEPSEEK_V4_FLASH:-}"
  AIRA_ENV_FILE="$main/.env" "$py" phase1/scripts/balance_guard.py deepseek 25
)

echo 'PREFLIGHT_10_WALLTIME_CONTAINER_AND_CLUSTER'
active_jobs=$(squeue -h -u "$USER" -o '%A' | sort -u | wc -l)
printf 'ACTIVE_JOB_COUNT_BEFORE_SUBMIT=%s\n' "$active_jobs"
test "$active_jobs" -le 3
container_sha=$(sha256sum "$container" | awk '{print $1}')
test "$container_sha" = "$expected_container_sha"
printf '%s\n' "$container_sha" > "$ops/prereg/container_sha256.txt"
bash -n "$generation_sbatch" "$replay_sbatch" "$watcher" "$hydra"
test "$(grep -c '^#SBATCH --gpus-per-node=4$' "$generation_sbatch")" -eq 1
test "$(grep -c '^#SBATCH --time=01:40:00$' "$generation_sbatch")" -eq 1
test "$(grep -c '^#SBATCH --array=0-15%4$' "$replay_sbatch")" -eq 1
test "$(grep -c '^#SBATCH --time=00:20:00$' "$replay_sbatch")" -eq 1
test "$(grep -c '^#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38$' "$generation_sbatch")" -eq 1
test "$(grep -c '^#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38$' "$replay_sbatch")" -eq 1
"$py" - <<'PY'
generation_gpu_h = 4 * (100 / 60)
replay_gpu_h = 16 * (20 / 60)
candidate_gpu_h = 32 * (600 / 3600)
assert abs(generation_gpu_h + replay_gpu_h - 12.0) < 1e-12
assert abs(candidate_gpu_h - 16 / 3) < 1e-12
print(f"BUDGET_PASS scheduler_gpu_h={generation_gpu_h + replay_gpu_h:.2f} candidate_gpu_h={candidate_gpu_h:.2f} logical_api_max=64")
PY

echo 'PREFLIGHT_11_DISCOVERY_POWER_SCOPE'
grep -q 'N=8 仅用于 safety/discovery' "$prereg_doc"
grep -q '不报告显著性' "$prereg_doc"

echo 'PREFLIGHT_12_TRUE_RC_CAPTURE'
grep -Fq 'worker_rc=$?' "$replay_sbatch"
grep -Fq 'generation_rc=$?' "$watcher"
grep -Fq 'extract_rc=$?' "$watcher"
grep -Fq 'validator_rc=$?' "$watcher"
grep -Fq 'independent_rc=$?' "$watcher"

echo 'PREFLIGHT_13_APPEND_ONLY_FREEZE'
remote=$(
  set +u
  source "$HOME/env_setup.sh"
  set -u
  git ls-remote fork refs/heads/phase1-value-critic | awk '{print $1}'
)
test "$remote" = "$commit"
test ! -e "$ops/runs/aira-dojo/user_yzyang4_issue_probe_contract_ab_safety_v2_original"
test ! -e "$ops/runs/aira-dojo/user_yzyang4_issue_probe_contract_ab_safety_v2_contract"
test ! -e "$ops/status"

echo 'HYDRA_RESOLVED_CONFIG_AND_PUBLIC_DATA_AUDIT'
"$hydra"

cp "$prereg_doc" "$ops/prereg/"
cp "$launcher" "$generation_sbatch" "$replay_sbatch" "$watcher" "$hydra" "$independent" "$ops/prereg/"
sha256sum \
  "$prereg_doc" \
  phase1/probe_contract_ab_common.py \
  phase1/probe_contract_ab_generation_entry.py \
  phase1/build_probe_contract_ab_manifest.py \
  phase1/extract_probe_contract_ab_manifest.py \
  phase1/validate_probe_contract_ab.py \
  phase1/validate_schema_probe_contract.py \
  phase1/schema_probe_contract_worker.py \
  phase1/audit_probe_contract_ab_hydra.py \
  phase1/verify_probe_contract_ab_v2_independent.py \
  src/dojo/configs/solver/operators/mlebench/aira_operators/draft.yaml \
  src/dojo/configs/solver/operators/mlebench/aira_operators/schema_probe_draft.yaml \
  "$launcher" "$generation_sbatch" "$replay_sbatch" "$watcher" "$hydra" \
  > "$ops/prereg/scientific_source_sha256.txt"

set +o pipefail
filename_count=$(find "$ops/prereg" -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)
content_count=$(grep -R -I -E \
  'AKIA[0-9A-Z]{16}|(^|[^A-Za-z])sk-[A-Za-z0-9._-]{12,}|BEGIN [A-Z ]*PRIVATE KEY|Bearer[[:space:]]+[A-Za-z0-9._-]{12,}' \
  "$ops/prereg" | wc -l)
set -o pipefail
printf 'PREREG_FILENAME_SECRET_COUNT=%s\n' "$filename_count"
printf 'PREREG_CONTENT_SECRET_COUNT=%s\n' "$content_count"
test "$filename_count" -eq 0
test "$content_count" -eq 0

echo 'ALL_PREFLIGHT_GATES_PASS_SUBMITTING'
set +e
generation_job=$(sbatch --parsable "$generation_sbatch")
submit_rc=$?
set -e
printf 'GENERATION_SUBMIT_RC=%s\n' "$submit_rc"
if [[ "$submit_rc" -ne 0 || -z "$generation_job" ]]; then
  exit 1
fi
printf '%s\n' "$generation_job" > "$ops/generation_job_id.txt"
monitor_out="$logs/probe_contract_ab_v2_monitor_20260813.out"
nohup env -i \
  HOME="$HOME" USER="$USER" PATH="$PATH" LANG="${LANG:-C.UTF-8}" \
  "$watcher" "$generation_job" > "$monitor_out" 2>&1 < /dev/null &
monitor_pid=$!
printf '%s\n' "$monitor_pid" > "$ops/monitor_pid.txt"
kill -0 "$monitor_pid"
printf 'PROBE_CONTRACT_AB_V2_SUBMITTED generation_job=%s monitor_pid=%s\n' \
  "$generation_job" "$monitor_pid"
