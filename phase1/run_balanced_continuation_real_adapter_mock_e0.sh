#!/usr/bin/env bash
# Formal zero-GPU Linux smoke for the real-adapter process boundary.
set -eo pipefail

if [[ -f "${HOME}/env_setup.sh" ]]; then
  # env_setup.sh is not nounset-safe on the cluster; source it before enabling -u.
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
base_repo="/research/d7/spc/yzyang4/aira-dojo"
worktree="/research/d7/spc/yzyang4/aira-dojo-adapter-mock-${short_commit}"
run_root="/research/d7/spc/yzyang4/balanced-real-adapter-mock-${short_commit}-a1"
log_root="/research/d7/spc/yzyang4/logs/balanced-real-adapter-mock-${short_commit}-a1"
archive="${run_root}.tar.gz"
python_bin="/research/d7/spc/yzyang4/venvs/exp/bin/python"

for required in "$base_repo" "$python_bin"; do
  if [[ ! -e "$required" ]]; then
    echo "required path absent: $required" >&2
    exit 3
  fi
done
for target in "$worktree" "$run_root" "$log_root" "$archive"; do
  if [[ -e "$target" || -L "$target" ]]; then
    echo "formal target already exists: $target" >&2
    exit 4
  fi
done

mkdir -p "$log_root"
git -C "$base_repo" fetch myfork codex-prospective-decision-v1-20260814 \
  >"${log_root}/fetch.stdout" 2>"${log_root}/fetch.stderr"
git -C "$base_repo" cat-file -e "${source_commit}^{commit}"
git -C "$base_repo" worktree add --detach "$worktree" "$source_commit" \
  >"${log_root}/worktree.stdout" 2>"${log_root}/worktree.stderr"

actual_commit="$(git -C "$worktree" rev-parse HEAD)"
if [[ "$actual_commit" != "$source_commit" ]]; then
  echo "worktree commit differs" >&2
  exit 5
fi
if [[ -n "$(git -C "$worktree" status --porcelain)" ]]; then
  echo "worktree is not clean" >&2
  exit 6
fi

cd "$worktree"
"$python_bin" -m pytest -q \
  phase1/tests/test_balanced_continuation_real_contract.py \
  phase1/tests/test_balanced_continuation_real_adapter_mock.py \
  phase1/tests/test_balanced_continuation_manifest.py \
  phase1/tests/test_balanced_continuation_worker.py \
  >"${log_root}/focused_tests.txt" 2>&1
"$python_bin" -m pytest -q phase1/tests \
  >"${log_root}/full_phase1_tests.txt" 2>&1

cat >"${log_root}/preflight.txt" <<'EOF'
PASS 1: direction is the run-clean decision-local benchmark; adapter smoke is gated engineering only
PASS 2: contract, mock adapter, independent verifier, assignment and worker tests passed before execution
PASS 3: one synthetic rollout and fixed H=1 fixture are declared; no scientific distribution is sampled
PASS 4: resource matrix is 1 rollout, 2 candidate processes, 0 Slurm/GPU/API requests
PASS 5: no training, frozen cohort, prospective vault or historical outcome is read
PASS 6: existing worker resume gate remains unchanged; this short smoke has no paid execution to resume
PASS 7: source, evaluator, split, operator, workspace and visibility hashes are frozen in one contract
PASS 8: fixed operator seed is recorded; finite-number and contradictory-state rejection are tested
PASS 9: child environment is allowlisted; credential scans are required before archive or push
PASS 10: every sidecar has a fixed 30-second wall cap; no E1 job is launched
PASS 11: smoke cannot unlock a method claim or E1/E2/E3
PASS 12: all seven child return codes are durably recorded and any nonzero code aborts
PASS 13: exact clean worktree and new output roots are required; receipts and hashes are append-only
EOF

"$python_bin" phase1/balanced_continuation_real_adapter_mock.py run \
  --output "$run_root" \
  --source-commit "$source_commit" \
  >"${log_root}/worker.stdout" 2>"${log_root}/worker.stderr"
"$python_bin" phase1/verify_balanced_continuation_real_adapter_mock.py \
  --input "$run_root" \
  --output "${log_root}/independent_verification.json" \
  >"${log_root}/verifier.stdout" 2>"${log_root}/verifier.stderr"

filename_hits="$(find "$run_root" -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$run_root" | wc -l)"
if [[ "$filename_hits" != "0" || "$content_hits" != "0" ]]; then
  echo "artifact secret scan failed: filename=${filename_hits} content=${content_hits}" >&2
  exit 7
fi
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' "$filename_hits" "$content_hits" \
  >"${log_root}/secret_scan.txt"

find "$run_root" -type f -print0 | sort -z | xargs -0 sha256sum \
  >"${log_root}/top_manifest.sha256"
tar -C "$(dirname "$run_root")" -czf "$archive" "$(basename "$run_root")"
sha256sum "$archive" >"${log_root}/archive.sha256"
printf '%s\n' \
  "STATUS=VERIFIED_ZERO_GPU_REAL_ADAPTER_MOCK" \
  "SOURCE_COMMIT=${source_commit}" \
  "WORKTREE=${worktree}" \
  "RUN_ROOT=${run_root}" \
  "LOG_ROOT=${log_root}" \
  "ARCHIVE=${archive}" \
  "SLURM_JOBS=0" \
  "GPU_JOBS=0" \
  "API_CALLS=0" \
  "SCIENTIFIC_OUTCOME_CLAIMED=false"
