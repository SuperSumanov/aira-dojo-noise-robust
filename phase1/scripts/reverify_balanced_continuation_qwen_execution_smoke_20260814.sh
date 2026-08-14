#!/usr/bin/env bash
# Zero-execution re-verification after repairing the independent receipt reader.
set -eo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
set -u
umask 077

commit="${1:?exact verifier source commit required}"
run_root="${2:?existing immutable smoke root required}"
branch=codex-prospective-decision-v1-20260814
base_repo=/research/d7/spc/yzyang4/aira-dojo
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
source_run=/research/d7/spc/yzyang4/balanced-e1-real-e59a759d-a1
probe_root=/research/d7/spc/yzyang4/balanced-e1-operator-probe-1fc6031-a1
source_root="/research/d7/spc/yzyang4/worktrees/e1q-verify-${commit:0:8}"
receipt="${run_root}/verification.${commit:0:8}.json"

test -d "$run_root"
test -d "$source_run"
test -d "$probe_root"
test ! -e "$receipt"
git -C "$base_repo" fetch fork "$branch"
test "$(git -C "$base_repo" rev-parse FETCH_HEAD)" = "$commit"
if [[ ! -e "$source_root" && ! -L "$source_root" ]]; then
  GIT_LFS_SKIP_SMUDGE=1 git -C "$base_repo" worktree add --detach "$source_root" "$commit"
fi
test "$(git -C "$source_root" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$source_root" status --porcelain)"

cd "$source_root"
PYTHONPATH="$source_root" "$python_bin" -m pytest -q \
  phase1/tests/test_balanced_continuation_qwen_execution_smoke.py
PYTHONPATH="$source_root" "$python_bin" -m \
  phase1.verify_balanced_continuation_qwen_execution_smoke \
  --source-root "$source_root" \
  --source-run-root "$source_run" \
  --probe-root "$probe_root" \
  --output-root "$run_root/outputs" \
  --workspace-root "$run_root/workspaces" \
  --job-rc-root "$run_root/job_rc" \
  --receipt "$receipt"

filename_hits="$(printf '%s\n' "$(basename "$receipt")" | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -IlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$receipt" | wc -l || true)"
test "$filename_hits" = 0
test "$content_hits" = 0
sha256sum "$receipt"
