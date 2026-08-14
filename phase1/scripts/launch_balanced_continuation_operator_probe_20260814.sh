#!/usr/bin/env bash
# Launch the frozen two-call operator conformance probe from a clean pinned worktree.
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: $0 SOURCE_COMMIT" >&2
  exit 2
fi
source_commit="$1"
short_commit="${source_commit:0:7}"
source_root="/research/d7/spc/yzyang4/aira-dojo-verify-${short_commit}"
run_root=/research/d7/spc/yzyang4/balanced-e1-real-e59a759d-a1
output_root="/research/d7/spc/yzyang4/balanced-e1-operator-probe-${short_commit}-a1"
log_root="/research/d7/spc/yzyang4/logs/balanced-e1-operator-probe-${short_commit}-a1"
credential_file=/research/d7/spc/yzyang4/aira-dojo/.env
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

for required in "$source_root" "$run_root" "$python_bin" "$credential_file"; do
  [[ -e "$required" ]] || { echo "required probe path absent: $required" >&2; exit 3; }
done
[[ ! -L "$credential_file" && "$(stat -c %a "$credential_file")" == 600 ]] || {
  echo "remote credential file must be regular mode 0600" >&2
  exit 4
}
[[ "$(git -C "$source_root" rev-parse HEAD)" == "$source_commit" ]] || {
  echo "probe worktree commit differs" >&2
  exit 5
}
[[ -z "$(git -C "$source_root" status --porcelain)" ]] || {
  echo "probe worktree is dirty" >&2
  exit 6
}
for target in "$output_root" "$log_root"; do
  [[ ! -e "$target" && ! -L "$target" ]] || {
    echo "probe target already exists: $target" >&2
    exit 7
  }
done

umask 077
mkdir "$log_root"
printf '%s\n' "$$" >"$log_root/launcher.pid"
set -a
source "$credential_file"
set +a
[[ -n "${PRIMARY_KEY_QWEN3_CODER_FLASH:-}" ]] || {
  echo "Qwen credential unavailable" >&2
  exit 8
}
cat >"$log_root/preflight.txt" <<EOF
status=PASS
source_commit=$source_commit
source_root=$source_root
source_clean=true
credential_mode=600
api_calls_cap=2
gpu_jobs_cap=0
candidate_executions_cap=0
sdk_retries=0
semantic_retries=0
EOF

set +e
PYTHONPATH="$source_root" "$python_bin" \
  -m phase1.balanced_continuation_operator_conformance_probe \
  --run-root "$run_root" \
  --output-root "$output_root" \
  >"$log_root/probe.stdout" 2>"$log_root/probe.stderr"
rc=$?
set -e
printf '%s\n' "$rc" >"$log_root/probe.rc.tmp"
mv "$log_root/probe.rc.tmp" "$log_root/probe.rc"
exit "$rc"
