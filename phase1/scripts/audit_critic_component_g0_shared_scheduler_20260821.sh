#!/usr/bin/env bash
# Read-only scheduler qualification for the shared Pro6000 G0 template.
# The only sbatch invocation uses --test-only and must leave the user's queue unchanged.
set -euo pipefail
umask 077

if (( $# != 3 )); then
  printf 'usage: %s CONTROL_ROOT EXPECTED_COMMIT OUTPUT_DIR\n' "$0" >&2
  exit 2
fi

readonly control_root=$(realpath "$1")
readonly expected_commit="$2"
readonly output_dir="$3"
readonly test_python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly runtime_python_bin=/research/d7/spc/yzyang4/venvs/critic/bin/python
readonly scheduler="$control_root/phase1/scripts/critic_component_g0_shared_pro6000_20260821.sbatch"
readonly audit_script="$control_root/phase1/scripts/audit_critic_component_g0_shared_scheduler_20260821.sh"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export BLIS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export PYTHONHASHSEED=0

case "$output_dir" in
  /research/d7/spc/yzyang4/critic-component-g0/scheduler-audits/*) ;;
  *)
    printf 'output directory is outside the fixed scheduler-audit root: %s\n' "$output_dir" >&2
    exit 2
    ;;
esac

test ! -e "$output_dir"
test -x "$test_python_bin"
test -x "$runtime_python_bin"
test -f "$scheduler"
test "$(git -C "$control_root" rev-parse HEAD)" = "$expected_commit"
test -z "$(git -C "$control_root" status --porcelain --untracked-files=all)"
cd "$control_root"

mkdir -m 0700 -p "$output_dir"
date -u +%Y-%m-%dT%H:%M:%SZ > "$output_dir/started_at_utc.txt"
git -C "$control_root" rev-parse HEAD > "$output_dir/control_commit.txt"
git -C "$control_root" status --porcelain --untracked-files=all > "$output_dir/git_status.txt"
sha256sum \
  "$audit_script" \
  "$scheduler" \
  "$control_root/phase1/scripts/critic_component_g0_worker_20260821.sh" \
  "$control_root/phase1/verify_critic_component_g0.py" \
  > "$output_dir/control_sha256.txt"

bash -n "$scheduler"
bash -n "$audit_script"
bash -n "$control_root/phase1/scripts/critic_component_g0_worker_20260821.sh"
"$test_python_bin" -m py_compile "$control_root/phase1/verify_critic_component_g0.py"
"$test_python_bin" -m pytest \
  "$control_root/phase1/tests/test_verify_critic_component_g0.py" -q \
  > "$output_dir/focused_tests.txt" 2> "$output_dir/focused_tests.stderr"
"$test_python_bin" -m pytest "$control_root/phase1/tests" -q \
  > "$output_dir/phase_tests.txt" 2> "$output_dir/phase_tests.stderr"

export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
sacctmgr -n -P show assoc user="$(id -un)" \
  format=Cluster,Account,User,Partition,QOS,DefaultQOS \
  > "$output_dir/association.txt"
scontrol show partition gpu_24h > "$output_dir/partition.txt"
scontrol show node projgpu39 > "$output_dir/node.txt"
squeue -u "$(id -un)" -h -o '%i|%P|%j|%T|%R' > "$output_dir/queue_before.txt"

sbatch --test-only \
  --export=ALL,G0_CONTROL_ROOT="$control_root" \
  "$scheduler" \
  > "$output_dir/scheduler_test.txt" 2>&1

squeue -u "$(id -un)" -h -o '%i|%P|%j|%T|%R' > "$output_dir/queue_after.txt"
diff -u "$output_dir/queue_before.txt" "$output_dir/queue_after.txt" > "$output_dir/queue.diff"

readonly hypothetical_job_id=$(awk '/Job [0-9]+ to start/ {print $3}' "$output_dir/scheduler_test.txt")
[[ "$hypothetical_job_id" =~ ^[0-9]+$ ]]
set +e
squeue -h -j "$hypothetical_job_id" > "$output_dir/hypothetical_lookup.stdout" \
  2> "$output_dir/hypothetical_lookup.stderr"
readonly lookup_rc=$?
set -e
printf '%s\n' "$lookup_rc" > "$output_dir/hypothetical_lookup.rc"
(( lookup_rc != 0 ))

printf '%s\n' \
  'status=G0_SHARED_SCHEDULER_TEST_ONLY_PASS' \
  'real_jobs_submitted=0' \
  'gpu_jobs_started=0' \
  'api_calls=0' \
  'test_pair_reads=0' \
  'scientific_outcomes=0' \
  'approval_to_submit=false' \
  > "$output_dir/summary.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$output_dir/completed_at_utc.txt"

find "$output_dir" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > "$output_dir/SHA256SUMS"
printf 'G0_SHARED_SCHEDULER_AUDIT_COMPLETE\n' > "$output_dir/COMPLETE"
chmod -R a-w "$output_dir"
