#!/usr/bin/env bash
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set +u
source "$HOME/env_setup.sh"
set -u

: "${1:?usage: watch_frozen_embed_discovery_20260814.sh EXPERIMENT_ROOT SMOKE_JOB}"
: "${2:?usage: watch_frozen_embed_discovery_20260814.sh EXPERIMENT_ROOT SMOKE_JOB}"
root=$1
smoke_job=$2
repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
py=/research/d7/spc/yzyang4/venvs/critic/bin/python
cards="$repo/phase1/cards_current_v11.jsonl"
manifest="$root/manifest/train_endpoints.jsonl"
manifest_summary="$root/manifest/train_endpoints_summary.json"
model=/research/d7/spc/yzyang4/external/models/qwen2.5-0.5b-instruct
commit=$(cat "$root/prereg/expected_commit.txt")
manifest_sha=$(cat "$root/prereg/manifest_sha256.txt")
cards_sha=$(cat "$root/prereg/cards_sha256.txt")
model_sha=$(cat "$root/prereg/model_sha256.txt")
run_map_sha=$(cat "$root/prereg/run_map_sha256.txt")
pairs_sha=$(cat "$root/prereg/train_pairs_sha256.txt")

on_exit() {
  watcher_rc=$?
  printf 'FROZEN_EMBED_WATCHER_EXIT rc=%s time=%s\n' \
    "$watcher_rc" "$(date --iso-8601=seconds)"
}
trap on_exit EXIT

wait_for_job() {
  local job_id=$1
  local label=$2
  while squeue -h -j "$job_id" | grep -q .; do
    state=$(squeue -h -j "$job_id" -o '%T|%M|%R' | paste -sd ';' -)
    printf 'FROZEN_EMBED_MONITOR time=%s label=%s job=%s state=%s\n' \
      "$(date --iso-8601=seconds)" "$label" "$job_id" "$state"
    sleep 30
  done
  printf 'FROZEN_EMBED_JOB_LEFT_QUEUE time=%s label=%s job=%s\n' \
    "$(date --iso-8601=seconds)" "$label" "$job_id"
}

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"

wait_for_job "$smoke_job" smoke
smoke_dir="$root/smoke/shard_0"
test -f "$smoke_dir/metadata.json"
set +e
"$py" phase1/check_frozen_embed_smoke.py \
  --smoke-dir "$smoke_dir" \
  --manifest-summary "$manifest_summary" \
  --manifest-sha256 "$manifest_sha" \
  --model-sha256 "$model_sha" \
  --commit "$commit" \
  --worker-source phase1/frozen_embed_worker.py \
  --out "$root/smoke/smoke_validation.json" \
  --max-extrapolated-s 12600
smoke_verify_rc=$?
set -e
printf 'FROZEN_EMBED_SMOKE_VERIFY_RC=%s time=%s\n' \
  "$smoke_verify_rc" "$(date --iso-8601=seconds)"
test "$smoke_verify_rc" -eq 0

# A second invocation must recognize the exact completed prefix and change no artifact.
find "$smoke_dir" -maxdepth 1 -type f -print0 | sort -z | xargs -0 sha256sum \
  > "$root/smoke/before_idempotent.sha256"
set +e
"$py" phase1/frozen_embed_worker.py \
  --cards "$cards" --manifest "$manifest" --model "$model" \
  --out-dir "$smoke_dir" --repo-root "$repo" \
  --shard 0 --num-shards 4 --max-len 8192 --head-fraction 0.25 \
  --batch-size 2 --chunk-size 32 --limit-cards 16 \
  --expect-cards-sha256 "$cards_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-model-sha256 "$model_sha" --expect-commit "$commit" \
  > "$root/smoke/idempotent_reentry.log" 2>&1
reentry_rc=$?
set -e
printf 'FROZEN_EMBED_REENTRY_RC=%s time=%s\n' \
  "$reentry_rc" "$(date --iso-8601=seconds)"
test "$reentry_rc" -eq 0
grep -q 'FROZEN_EMBED_WORKER_ALREADY_COMPLETE' "$root/smoke/idempotent_reentry.log"
find "$smoke_dir" -maxdepth 1 -type f -print0 | sort -z | xargs -0 sha256sum \
  > "$root/smoke/after_idempotent.sha256"
cmp "$root/smoke/before_idempotent.sha256" "$root/smoke/after_idempotent.sha256"

active_jobs=$(squeue -h -u yzyang4 | wc -l)
while [[ "$active_jobs" -ne 0 ]]; do
  printf 'FROZEN_EMBED_WAITING_FOR_FOUR_JOB_CAPACITY time=%s active=%s\n' \
    "$(date --iso-8601=seconds)" "$active_jobs"
  sleep 30
  active_jobs=$(squeue -h -u yzyang4 | wc -l)
done
printf 'FROZEN_EMBED_ACTIVE_BEFORE_FULL=%s\n' "$active_jobs"
full_job=$(sbatch --parsable \
  --export="ALL,EXPERIMENT_ROOT=$root,EXPECTED_COMMIT=$commit,EXPECTED_MANIFEST_SHA=$manifest_sha,EXPECTED_CARDS_SHA=$cards_sha,EXPECTED_MODEL_SHA=$model_sha" \
  phase1/frozen_embed_full_20260814.sbatch)
printf '%s\n' "$full_job" > "$root/full_job_id.txt"
printf 'FROZEN_EMBED_FULL_SUBMITTED time=%s job=%s\n' \
  "$(date --iso-8601=seconds)" "$full_job"

wait_for_job "$full_job" full
for shard in 0 1 2 3; do
  metadata="$root/features/shard_${shard}/metadata.json"
  test -f "$metadata"
  test "$(jq -r '.status' "$metadata")" = COMPLETE
  test "$(jq -r '.git_commit' "$metadata")" = "$commit"
  test "$(jq -r '.config.limit_cards' "$metadata")" = 0
done

rank_out="$root/rank"
set +e
timeout --signal=TERM --kill-after=30s 900s \
  "$py" phase1/frozen_embed_rank.py \
  --pairs phase1/v11_decision/decision_train_v11_b0.jsonl \
  --run-map phase1/card_run_map.json \
  --manifest "$manifest" \
  --manifest-summary "$manifest_summary" \
  --feature-root "$root/features" \
  --model-sha256 "$model_sha" \
  --repo-root "$repo" \
  --out-dir "$rank_out" \
  --expect-pairs-sha256 "$pairs_sha" \
  --expect-run-map-sha256 "$run_map_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-commit "$commit" \
  --wall-cap-s 900 \
  > "$root/rank.log" 2>&1
rank_rc=$?
set -e
printf 'FROZEN_EMBED_RANK_RC=%s time=%s\n' "$rank_rc" "$(date --iso-8601=seconds)"
test "$rank_rc" -eq 0

set +e
"$py" phase1/verify_frozen_embed_discovery.py \
  --summary "$rank_out/summary.json" \
  --predictions "$rank_out/oof_predictions.csv" \
  --pairs phase1/v11_decision/decision_train_v11_b0.jsonl \
  --run-map phase1/card_run_map.json \
  --manifest "$manifest" \
  --manifest-summary "$manifest_summary" \
  --feature-root "$root/features" \
  --rank-source phase1/frozen_embed_rank.py \
  --worker-source phase1/frozen_embed_worker.py \
  --repo-root "$repo" \
  --expect-commit "$commit" \
  --expect-model-sha256 "$model_sha" \
  --out "$rank_out/independent_verify.json" \
  > "$root/verify.log" 2>&1
verify_rc=$?
set -e
printf 'FROZEN_EMBED_VERIFY_RC=%s time=%s\n' "$verify_rc" "$(date --iso-8601=seconds)"
test "$verify_rc" -eq 0

jq '{status,frozen_read,primary_pair_accuracy,complete_parent_top1,parent_equal_gap_utility,task_consistency,discovery_gate}' \
  "$rank_out/summary.json"
printf 'FROZEN_EMBED_DISCOVERY_CHAIN_DONE time=%s status=%s\n' \
  "$(date --iso-8601=seconds)" "$(jq -r '.status' "$rank_out/summary.json")"
