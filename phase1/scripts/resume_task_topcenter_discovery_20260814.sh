#!/usr/bin/env bash
set -eo pipefail

source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repo=$(cd "$script_dir/../.." && pwd -P)
python=/research/d7/spc/yzyang4/venvs/critic/bin/python
feature_run=/research/d7/spc/yzyang4/experiments/frozen_embed_v11_20260814_f339eb971c6d
train_pairs=phase1/v11_decision/decision_train_v11_b0.jsonl
run_map=phase1/card_run_map.json
manifest="$feature_run/manifest/train_endpoints.jsonl"
manifest_summary="$feature_run/manifest/train_endpoints_summary.json"
feature_root="$feature_run/features"
baseline_oof="$feature_run/rank/oof_predictions.csv"
pair_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
run_map_sha=3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30
manifest_sha=8c9621dd9d863d5640c54d1eefee42f5c170bbaf5d7bceceda7aa372ac1afc19
baseline_sha=083f4daa23ab3f8b1d9e412184fbe9ee06d891385e8f66e0bbbb29b3e3055a96
model_sha=fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe
extraction_commit=f339eb971c6d04fd149c608cc570b4bcdcdd1aac

cd "$repo"
test "$(pwd -P)" = "$repo"
commit=$(git rev-parse HEAD)
root=/research/d7/spc/yzyang4/experiments/task_topcenter_v11_20260814_${commit:0:12}
test -d "$root"
test -f "$root/prereg/expected_commit.txt"
test "$(cat "$root/prereg/expected_commit.txt")" = "$commit"
test -f "$root/preflight.log"
grep -q 'PREFLIGHT_ALL_13_PASS' "$root/preflight.log"
if [[ -f "$root/rank/summary.json" ]]; then
  echo "ABORT_ALREADY_COMPLETE $root" >&2
  exit 2
fi
exec > >(tee -a "$root/resume.log") 2>&1
echo "RESUME_BEGIN $(date -Is) $commit"

set +e
timeout --signal=TERM 2700 "$python" phase1/task_topcenter_rank.py \
  --repo-root "$repo" \
  --pairs "$train_pairs" \
  --run-map "$run_map" \
  --manifest "$manifest" \
  --manifest-summary "$manifest_summary" \
  --feature-root "$feature_root" \
  --baseline-oof "$baseline_oof" \
  --out-dir "$root/rank" \
  --extraction-commit "$extraction_commit" \
  --model-sha256 "$model_sha" \
  --expect-pairs-sha256 "$pair_sha" \
  --expect-run-map-sha256 "$run_map_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-baseline-sha256 "$baseline_sha" \
  --wall-cap-s 2700
producer_rc=$?
set -e
echo "RESUME_PRODUCER_RC $producer_rc"
if [[ "$producer_rc" -ne 0 ]]; then
  exit "$producer_rc"
fi

set +e
"$python" phase1/verify_task_topcenter_discovery.py \
  --pairs "$train_pairs" \
  --manifest "$manifest" \
  --feature-root "$feature_root" \
  --baseline-oof "$baseline_oof" \
  --result-dir "$root/rank" \
  --output "$root/rank/independent_verify.json" \
  --expect-pairs-sha256 "$pair_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-baseline-sha256 "$baseline_sha" \
  --extraction-commit "$extraction_commit" \
  --model-sha256 "$model_sha"
verifier_rc=$?
set -e
echo "RESUME_VERIFIER_RC $verifier_rc"
if [[ "$verifier_rc" -ne 0 ]]; then
  exit "$verifier_rc"
fi
find "$root" -type f ! -name 'artifact_manifest*.sha256*' -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$root/artifact_manifest.resume.sha256"
echo "RESUME_CHAIN_COMPLETE $root $(date -Is)"
