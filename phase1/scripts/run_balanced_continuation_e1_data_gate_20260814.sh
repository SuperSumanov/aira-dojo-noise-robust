#!/usr/bin/env bash
# Formal zero-GPU gate for real E1 anchors and 80/10/10 evaluation data.
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
worktree="/research/d7/spc/yzyang4/aira-dojo-e1-data-${short_commit}"
run_root="/research/d7/spc/yzyang4/balanced-e1-data-${short_commit}-a1"
log_root="/research/d7/spc/yzyang4/logs/balanced-e1-data-${short_commit}-a1"
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
cards="${base_repo}/phase1/cards_current_v11.jsonl"
data_root=/research/d7/spc/yzyang4/mle-bench-data

for required in "$base_repo" "$python_bin" "$cards" "$data_root"; do
  if [[ ! -e "$required" ]]; then
    echo "required path absent: $required" >&2
    exit 3
  fi
done
for target in "$worktree" "$run_root" "$log_root"; do
  if [[ -e "$target" || -L "$target" ]]; then
    echo "formal target already exists: $target" >&2
    exit 4
  fi
done

mkdir -p "$log_root"
git -C "$base_repo" fetch fork codex-prospective-decision-v1-20260814 \
  >"${log_root}/fetch.stdout" 2>"${log_root}/fetch.stderr"
git -C "$base_repo" cat-file -e "${source_commit}^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "$base_repo" worktree add --detach "$worktree" "$source_commit" \
  >"${log_root}/worktree.stdout" 2>"${log_root}/worktree.stderr"
if [[ "$(git -C "$worktree" rev-parse HEAD)" != "$source_commit" ]]; then
  echo "worktree commit differs" >&2
  exit 5
fi
if [[ -n "$(git -C "$worktree" status --porcelain)" ]]; then
  echo "worktree is not clean" >&2
  exit 6
fi

cd "$worktree"
"$python_bin" -m pytest -q \
  phase1/tests/test_balanced_continuation_e1_inputs.py \
  phase1/tests/test_balanced_continuation_e1_split.py \
  phase1/tests/test_balanced_continuation_e1_scoring.py \
  phase1/tests/test_balanced_continuation_manifest.py \
  phase1/tests/test_balanced_continuation_worker.py \
  phase1/tests/test_balanced_continuation_real_contract.py \
  phase1/tests/test_balanced_continuation_real_adapter_mock.py \
  >"${log_root}/focused_tests.txt" 2>&1
"$python_bin" -m pytest -q phase1/tests >"${log_root}/full_phase1_tests.txt" 2>&1

mkdir "$run_root"
cp "$0" "${run_root}/launcher.sh"
printf '%s\n' "$source_commit" >"${run_root}/source_commit.txt"
cat >"${run_root}/preflight.txt" <<'EOF'
PASS 1: stable mainline remains run-clean decision-local benchmark; E1 is a gated extension
PASS 2: input/split/scorer/contract/manifest/worker tests pass before real-data construction
PASS 3: task support is reconstructed from v11 structure and b0 parent metadata before outcomes
PASS 4: this gate requests 0 Slurm jobs, 0 GPUs and 0 API calls
PASS 5: selected runs exclude v11 hold runs; frozen files are read for identity-only overlap audit
PASS 6: no paid rollout occurs and therefore no paid state is resumed or replaced
PASS 7: source files, split seed, task schemas and evaluator bundles are hash locked
PASS 8: split assignment is deterministic by full SHA-256; NaN/invalid submissions fail closed
PASS 9: no credentials are accepted in selected code; final filename/content scans are mandatory
PASS 10: both real tasks are rebuilt and independently rescanned before any GPU wall-clock smoke
PASS 11: data-gate success cannot establish balanced-label or search-utility benefit
PASS 12: shell pipefail and exact Python return codes abort before promotion on any failure
PASS 13: exact clean worktree and new append-only output roots are required
EOF

"$python_bin" -m phase1.build_balanced_continuation_e1_inputs \
  --cards "$cards" \
  --hold "$worktree/phase1/v11_decision/runsplit_holdruns_v11.json" \
  --decision-train-b0 "$worktree/phase1/v11_decision/decision_train_v11_b0.jsonl" \
  --frozen-b0 "$worktree/phase1/v11_decision/decision_frozen_v11_b0.jsonl" \
  --frozen-b1 "$worktree/phase1/v11_decision/decision_frozen_v11_b1.jsonl" \
  --frozen-b2 "$worktree/phase1/v11_decision/decision_frozen_v11_b2.jsonl" \
  --output "$run_root/e1_inputs" \
  >"${log_root}/input_builder.stdout" 2>"${log_root}/input_builder.stderr"
"$python_bin" -m phase1.verify_balanced_continuation_e1_inputs \
  --cards "$cards" \
  --hold "$worktree/phase1/v11_decision/runsplit_holdruns_v11.json" \
  --decision-train-b0 "$worktree/phase1/v11_decision/decision_train_v11_b0.jsonl" \
  --frozen-b0 "$worktree/phase1/v11_decision/decision_frozen_v11_b0.jsonl" \
  --frozen-b1 "$worktree/phase1/v11_decision/decision_frozen_v11_b1.jsonl" \
  --frozen-b2 "$worktree/phase1/v11_decision/decision_frozen_v11_b2.jsonl" \
  --result "$run_root/e1_inputs" \
  --receipt "$run_root/e1_inputs.verify.json" \
  >"${log_root}/input_verifier.stdout" 2>"${log_root}/input_verifier.stderr"

"$python_bin" -m phase1.balanced_continuation_e1_split \
  --source-root "$data_root" \
  --output "$run_root/e1_split" \
  >"${log_root}/split_builder.stdout" 2>"${log_root}/split_builder.stderr"
"$python_bin" -m phase1.verify_balanced_continuation_e1_split \
  --source-root "$data_root" \
  --result "$run_root/e1_split" \
  --receipt "$run_root/e1_split.verify.json" \
  >"${log_root}/split_verifier.stdout" 2>"${log_root}/split_verifier.stderr"

filename_hits="$(find "$run_root" -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$run_root" | wc -l || true)"
if [[ "$filename_hits" != 0 || "$content_hits" != 0 ]]; then
  echo "artifact safety scan failed: filename=${filename_hits} content=${content_hits}" >&2
  exit 7
fi
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' "$filename_hits" "$content_hits" \
  >"${run_root}/safety_scan.txt"
find "$run_root" -type f ! -name top_manifest.sha256 -print0 | sort -z | xargs -0 sha256sum \
  >"${run_root}/top_manifest.sha256"

printf '%s\n' \
  "STATUS=VERIFIED_E1_REAL_INPUT_AND_SPLIT_GATE" \
  "SOURCE_COMMIT=${source_commit}" \
  "WORKTREE=${worktree}" \
  "RUN_ROOT=${run_root}" \
  "LOG_ROOT=${log_root}" \
  "SLURM_JOBS=0" \
  "GPU_JOBS=0" \
  "API_CALLS=0" \
  "SCIENTIFIC_OUTCOME_CLAIMED=false"
