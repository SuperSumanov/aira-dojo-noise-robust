#!/usr/bin/env bash
set -euo pipefail

set +u
source "$HOME/env_setup.sh"
set -u

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
python=/research/d7/spc/yzyang4/venvs/critic/bin/python
expected_ref=fork/codex-parent-patch-critic-20260814
cards="$repo/phase1/cards_current_v11.jsonl"
run_map="$repo/phase1/card_run_map.json"
train="$repo/phase1/v11_decision/decision_train_v11_b0.jsonl"
frozen="$repo/phase1/v11_decision/decision_frozen_v11_b0.jsonl"
prereg="$repo/phase1/实验记录/2026-08-14/ParentPatchCritic_CPU发现门_预注册.md"

commit=$(git -C "$repo" rev-parse HEAD)
expected_commit=$(git -C "$repo" rev-parse "$expected_ref")
test "$commit" = "$expected_commit"
test -z "$(git -C "$repo" status --porcelain)"

echo PARENT_PATCH_PREFLIGHT_INPUT_HASHES
printf '%s  %s\n' \
  6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75 "$cards" \
  3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30 "$run_map" \
  bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca "$train" \
  2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8 "$frozen" \
  | sha256sum --check --strict

if head -1 "$cards" | grep -Fq 'version https://git-lfs.github.com/spec/v1'; then
  echo PARENT_PATCH_ABORT_CARDS_IS_LFS_POINTER >&2
  exit 2
fi

test "$(wc -l < "$cards" | tr -d '[:space:]')" = 16012
test "$(wc -l < "$train" | tr -d '[:space:]')" = 4263
test "$(wc -l < "$frozen" | tr -d '[:space:]')" = 1498

experiment_root=/research/d7/spc/yzyang4/experiments
out="$experiment_root/parent_patch_sparse_v3_20260814_${commit:0:12}"
mkdir -p "$experiment_root"
if [[ -e "$out" ]]; then
  echo PARENT_PATCH_ABORT_OUTPUT_ALREADY_EXISTS="$out" >&2
  exit 2
fi
mkdir "$out"

export PYTHONHASHSEED=887
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

{
  echo PARENT_PATCH_RUN_START="$(date --iso-8601=seconds)"
  echo HOST="$(hostname)"
  echo COMMIT="$commit"
  echo SOURCE_SHA256="$(sha256sum "$repo/phase1/parent_patch_gate.py" | awk '{print $1}')"
  echo VERIFIER_SHA256="$(sha256sum "$repo/phase1/verify_parent_patch_gate.py" | awk '{print $1}')"
  echo PREREG_SHA256="$(sha256sum "$prereg" | awk '{print $1}')"
} | tee "$out/launcher.log"

set +e
timeout --signal=TERM --kill-after=30s 900s \
  "$python" "$repo/phase1/parent_patch_gate.py" \
  --cards "$cards" \
  --run-map "$run_map" \
  --train-pairs "$train" \
  --frozen-pairs "$frozen" \
  --prereg "$prereg" \
  --out-dir "$out" \
  --repo-root "$repo" \
  --wall-cap-s 900 \
  >> "$out/launcher.log" 2>&1
gate_rc=$?
set -e
echo GATE_RC="$gate_rc" | tee -a "$out/launcher.log"
if [[ "$gate_rc" -ne 0 ]]; then
  echo PARENT_PATCH_GATE_FAILED out="$out" rc="$gate_rc"
  exit "$gate_rc"
fi

verify_args=(
  --summary "$out/summary.json"
  --oof "$out/oof_predictions.csv"
  --out "$out/independent_verify.json"
)
if [[ -f "$out/frozen_predictions.csv" ]]; then
  verify_args+=(--frozen "$out/frozen_predictions.csv")
fi

set +e
"$python" "$repo/phase1/verify_parent_patch_gate.py" "${verify_args[@]}" \
  >> "$out/launcher.log" 2>&1
verify_rc=$?
set -e
echo VERIFY_RC="$verify_rc" | tee -a "$out/launcher.log"
test "$verify_rc" -eq 0

echo PARENT_PATCH_RUN_DONE="$(date --iso-8601=seconds)" | tee -a "$out/launcher.log"
echo PARENT_PATCH_OUTPUT="$out"
