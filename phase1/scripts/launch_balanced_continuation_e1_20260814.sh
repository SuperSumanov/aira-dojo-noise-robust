#!/usr/bin/env bash
# Formal preflight, preparation, capability gate, and phased submission for approved E1.
set -eo pipefail

if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: $0 SOURCE_COMMIT" >&2
  exit 2
fi
source_commit="$1"
short_commit="${source_commit:0:8}"
base_repo=/research/d7/spc/yzyang4/aira-dojo
source_root="/research/d7/spc/yzyang4/aira-dojo-e1-real-${short_commit}"
run_root="/research/d7/spc/yzyang4/balanced-e1-real-${short_commit}-a1"
external_log_root="/research/d7/spc/yzyang4/logs/balanced-e1-real-${short_commit}-a1"
data_gate=/research/d7/spc/yzyang4/balanced-e1-data-acd215a9-a1
cards="${base_repo}/phase1/cards_current_v11.jsonl"
data_source=/research/d7/spc/yzyang4/mle-bench-data
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
container="${base_repo}/build/superimage/superimage.root.2026-07-macos-v1.sif"
hf_cache=/research/d7/spc/yzyang4/scratch/hf_cache

for required in "$base_repo" "$data_gate" "$cards" "$data_source" "$python_bin" "$container" "$hf_cache"; do
  if [[ ! -e "$required" ]]; then
    echo "required E1 preflight path absent: $required" >&2
    exit 3
  fi
done
for target in "$source_root" "$run_root" "$external_log_root"; do
  if [[ -e "$target" || -L "$target" ]]; then
    echo "formal E1 target already exists: $target" >&2
    exit 4
  fi
done
if [[ -z "${PRIMARY_KEY_DEEPSEEK_V4_FLASH:-}" && -z "${PRIMARY_KEY:-}" ]]; then
  echo "E1 operator credential unavailable in remote environment" >&2
  exit 5
fi

mkdir -p "$external_log_root"
git -C "$base_repo" fetch fork codex-prospective-decision-v1-20260814 \
  >"${external_log_root}/fetch.stdout" 2>"${external_log_root}/fetch.stderr"
git -C "$base_repo" cat-file -e "${source_commit}^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "$base_repo" worktree add --detach "$source_root" "$source_commit" \
  >"${external_log_root}/worktree.stdout" 2>"${external_log_root}/worktree.stderr"
test "$(git -C "$source_root" rev-parse HEAD)" = "$source_commit"
test -z "$(git -C "$source_root" status --porcelain)"

mkdir "$run_root"
mkdir \
  "$run_root/preflight_receipts" "$run_root/worker_outputs" "$run_root/workspaces" \
  "$run_root/sealed" "$run_root/worker_receipts" "$run_root/job_logs" \
  "$run_root/job_rc" "$run_root/slurm" "$run_root/nvfix" "$run_root/capability"
cp "$0" "$run_root/launcher.sh"
cp "$source_root/phase1/scripts/monitor_balanced_continuation_e1_20260814.sh" \
  "$run_root/monitor.sh"
cp "$source_root/phase1/balanced_continuation_e1_20260814.sbatch" "$run_root/job.sbatch"
cp "$source_root/phase1/实验记录/2026-08-14/BalancedContinuation_E1_真实预注册.md" \
  "$run_root/frozen_prereg.md"
printf '%s\n' "$source_commit" >"$run_root/source_commit.txt"
printf '%s\n' "$data_gate" >"$run_root/data_gate_root.txt"

cd "$source_root"
"$python_bin" -m pytest -q \
  phase1/tests/test_balanced_continuation_e1_inputs.py \
  phase1/tests/test_balanced_continuation_e1_split.py \
  phase1/tests/test_balanced_continuation_e1_scoring.py \
  phase1/tests/test_balanced_continuation_manifest.py \
  phase1/tests/test_balanced_continuation_worker.py \
  phase1/tests/test_balanced_continuation_real_contract.py \
  phase1/tests/test_balanced_continuation_operator_entry.py \
  phase1/tests/test_balanced_continuation_real_worker.py \
  phase1/tests/test_prepare_balanced_continuation_e1.py \
  phase1/tests/test_verify_balanced_continuation_real_worker.py \
  phase1/tests/test_verify_balanced_continuation_e1_collection.py \
  phase1/tests/test_balanced_continuation_capability_probe.py \
  >"${external_log_root}/focused_tests.txt" 2>&1
"$python_bin" -m pytest -q phase1/tests \
  >"${external_log_root}/full_phase1_tests.txt" 2>&1

(cd "$data_gate" && sha256sum -c top_manifest.sha256) \
  >"${external_log_root}/data_gate_manifest_check.txt" 2>&1
"$python_bin" -m phase1.verify_balanced_continuation_e1_inputs \
  --cards "$cards" \
  --hold "$source_root/phase1/v11_decision/runsplit_holdruns_v11.json" \
  --decision-train-b0 "$source_root/phase1/v11_decision/decision_train_v11_b0.jsonl" \
  --frozen-b0 "$source_root/phase1/v11_decision/decision_frozen_v11_b0.jsonl" \
  --frozen-b1 "$source_root/phase1/v11_decision/decision_frozen_v11_b1.jsonl" \
  --frozen-b2 "$source_root/phase1/v11_decision/decision_frozen_v11_b2.jsonl" \
  --result "$data_gate/e1_inputs" \
  --receipt "$run_root/preflight_receipts/e1_inputs.verify.json" \
  >"${external_log_root}/input_verify.stdout" 2>"${external_log_root}/input_verify.stderr"
"$python_bin" -m phase1.verify_balanced_continuation_e1_split \
  --source-root "$data_source" \
  --result "$data_gate/e1_split" \
  --receipt "$run_root/preflight_receipts/e1_split.verify.json" \
  >"${external_log_root}/split_verify.stdout" 2>"${external_log_root}/split_verify.stderr"

"$python_bin" -m phase1.prepare_balanced_continuation_e1 \
  --data-gate "$data_gate" \
  --container "$container" \
  --output "$run_root/preparation" \
  --created-utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >"${external_log_root}/prepare.stdout" 2>"${external_log_root}/prepare.stderr"
"$python_bin" -m phase1.verify_balanced_continuation_manifest \
  --result "$run_root/preparation/assignment" \
  --receipt "$run_root/preflight_receipts/assignment.verify.json" \
  >"${external_log_root}/assignment_verify.stdout" \
  2>"${external_log_root}/assignment_verify.stderr"

cp /usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4 "$run_root/nvfix/libnvidia-nvvm.so.4"
chmod 0555 "$run_root/nvfix"
chmod 0444 "$run_root/nvfix/libnvidia-nvvm.so.4"

cp "$source_root/phase1/balanced_continuation_capability_probe.py" \
  "$run_root/capability/solution.py"
cap_public="$data_gate/e1_split/public/spaceship-titanic"
cap_binds="$run_root/capability:/workspace,$cap_public:/workspace/data:ro,$hf_cache:/hf:ro"
env -i PATH="$PATH" HOME=/tmp USER="$(id -un)" \
  singularity exec --containall --cleanenv --net --network none \
  --no-home --no-mount bind-paths --no-eval --pwd /workspace \
  --bind "$cap_binds" \
  "$container" env PYTHONUNBUFFERED=1 HOME=/tmp HF_HOME=/hf HF_HUB_OFFLINE=1 \
  python solution.py \
  >"${external_log_root}/capability.stdout" 2>"${external_log_root}/capability.stderr"
grep -q 'E1_CONTAINER_CAPABILITY_PASS' "${external_log_root}/capability.stdout"

"$python_bin" - "$run_root/preparation/run_plan.json" "$run_root/preflight_matrix.json" <<'PY'
import json, pathlib, sys
plan = json.load(open(sys.argv[1]))
required = {
    "rollout_jobs": 8,
    "candidate_executions": 16,
    "operator_api_calls": 8,
    "expected_gpu_hours": 3.24,
    "candidate_timeout_seconds": 600,
    "slurm_array_concurrency": 4,
    "gpus_per_job": 1,
    "e2_e3_authorized": False,
}
if any(plan.get(key) != value for key, value in required.items()):
    raise SystemExit("E1 run-plan resource matrix differs")
if len(plan["stage_one_engineering_gate_indices"]) != 4 or len(plan["stage_two_remaining_indices"]) != 4:
    raise SystemExit("E1 stage sizes differ")
pathlib.Path(sys.argv[2]).write_text(json.dumps({"verified": required, "stage_one": plan["stage_one_engineering_gate_indices"], "stage_two": plan["stage_two_remaining_indices"]}, sort_keys=True, separators=(",", ":")) + "\n")
print(json.dumps(plan, sort_keys=True, separators=(",", ":")))
PY

cat >"$run_root/preflight_before_stage1.txt" <<'EOF'
PASS 1: stable mainline remains run-clean decision-local benchmark; V_H estimand, three later primary gates and E1 retraction boundary are frozen
PASS 2: producer, independent input/split/assignment/worker/collection verifiers, state machine, evaluator and capability tests passed
PASS 3: two tasks, one anchor/task, two exact-code-distinct siblings and pre-outcome eligible-parent/run support are printed in the verified data gate
PASS 4: actual plan prints 8 jobs, 16 candidate attempts, 8 API calls, expected 3.24 GPU-hours, one GPU/job and array concurrency four
PASS 5: selected physical runs have zero frozen endpoint/run overlap; first-960/prospective/D_test are not read
PASS 6: durable intent precedes paid action; incomplete PENDING is ambiguous and cannot retry or receive a replacement
PASS 7: source/container/operator/prompt/data/split/evaluator/timeout/workspace contracts are hash-bound and identical across all assignments
PASS 8: blocked assignment and request seeds are recorded; finite-number, direction, invalid-format and timeout paths have regression coverage
PASS 9: credentials come only from the remote environment; candidate env is allowlisted and filename/content scans are mandatory per job
PENDING 10: stage one is exactly one complete block per task; stage two has an afterok dependency and cannot start until all four commitment-only verifiers pass
PASS 11: E1 is engineering/descriptive only, cannot claim a primary gate or unlock E2/E3, and forbids outcome-driven retuning
PASS 12: worker/verifier/safety rc are written per array index; dependency failure stops the remaining chain
PASS 13: exact clean source, new run roots, atomic per-rollout artifacts and recursive SHA manifests are required
EOF

filename_hits="$(find "$run_root/preparation" "$run_root/preflight_receipts" "$run_root/frozen_prereg.md" \
  -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$run_root/preparation" "$run_root/preflight_receipts" "$run_root/frozen_prereg.md" | wc -l || true)"
if [[ "$filename_hits" != 0 || "$content_hits" != 0 ]]; then
  echo "E1 preflight artifact safety scan failed: filename=$filename_hits content=$content_hits" >&2
  exit 7
fi
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' "$filename_hits" "$content_hits" \
  >"$run_root/preflight_safety_scan.txt"

stage_one="$($python_bin -c 'import json,sys;print(",".join(map(str,json.load(open(sys.argv[1]))["stage_one_engineering_gate_indices"])))' "$run_root/preparation/run_plan.json")"
stage_two="$($python_bin -c 'import json,sys;print(",".join(map(str,json.load(open(sys.argv[1]))["stage_two_remaining_indices"])))' "$run_root/preparation/run_plan.json")"
export_spec="ALL,E1_RUN_ROOT=${run_root},E1_SOURCE_ROOT=${source_root},E1_DATA_GATE_ROOT=${data_gate}"
stage_one_submit="$(sbatch --parsable --array="${stage_one}%4" \
  --export="$export_spec" \
  --output="$run_root/slurm/stage1_%A_%a.out" \
  --error="$run_root/slurm/stage1_%A_%a.err" \
  "$run_root/job.sbatch")"
stage_one_job="${stage_one_submit%%;*}"
stage_two_submit="$(sbatch --parsable --dependency="afterok:${stage_one_job}" \
  --array="${stage_two}%4" \
  --export="$export_spec" \
  --output="$run_root/slurm/stage2_%A_%a.out" \
  --error="$run_root/slurm/stage2_%A_%a.err" \
  "$run_root/job.sbatch")"
stage_two_job="${stage_two_submit%%;*}"
printf '{"stage_one_job":"%s","stage_two_job":"%s","stage_one_indices":"%s","stage_two_indices":"%s"}\n' \
  "$stage_one_job" "$stage_two_job" "$stage_one" "$stage_two" >"$run_root/submission.json"

# Start the score-blind monitor from the hash-bound run copy so the phased gate
# survives the invoking SSH session.  Its stdout/stderr live outside the
# immutable result tree; all decisions and terminal status are also appended
# inside run_root by monitor.sh.
nohup bash "$run_root/monitor.sh" \
  "$run_root" "$source_root" "$data_gate" "$stage_one_job" "$stage_two_job" \
  >"${external_log_root}/monitor.stdout" \
  2>"${external_log_root}/monitor.stderr" </dev/null &
monitor_pid="$!"
printf '%s\n' "$monitor_pid" >"$run_root/monitor.pid"

printf '%s\n' \
  "STATUS=E1_PHASED_SUBMITTED" \
  "SOURCE_COMMIT=${source_commit}" \
  "SOURCE_ROOT=${source_root}" \
  "RUN_ROOT=${run_root}" \
  "EXTERNAL_LOG_ROOT=${external_log_root}" \
  "STAGE_ONE_JOB=${stage_one_job}" \
  "STAGE_TWO_JOB=${stage_two_job}" \
  "MONITOR_PID=${monitor_pid}" \
  "STAGE_ONE_INDICES=${stage_one}" \
  "STAGE_TWO_INDICES=${stage_two}" \
  "EXPECTED_ROLLOUTS=8" \
  "EXPECTED_CANDIDATE_EXECUTIONS=16" \
  "EXPECTED_OPERATOR_API_CALLS=8" \
  "EXPECTED_GPU_HOURS=3.24" \
  "E2_E3_AUTHORIZED=false"
