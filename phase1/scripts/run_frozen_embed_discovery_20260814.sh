#!/usr/bin/env bash
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set +u
source "$HOME/env_setup.sh"
set -u

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
py=/research/d7/spc/yzyang4/venvs/critic/bin/python
expected_ref=fork/codex-frozen-embed-v11-20260814
cards="$repo/phase1/cards_current_v11.jsonl"
pairs="$repo/phase1/v11_decision/decision_train_v11_b0.jsonl"
run_map="$repo/phase1/card_run_map.json"
split="$repo/phase1/v11_decision/runsplit_holdruns_v11.json"
model=/research/d7/spc/yzyang4/external/models/qwen2.5-0.5b-instruct
cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
pairs_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
run_map_sha=3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30
split_sha=b31bd70a4483ac1ca207eae47ae39d7b00ced1b02c81583d0b0447fdd3d8489b
model_sha=fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe

cd "$repo"
commit=$(git rev-parse HEAD)
expected_commit=$(git rev-parse "$expected_ref")
test "$commit" = "$expected_commit"
test -z "$(git status --short)"
root="/research/d7/spc/yzyang4/experiments/frozen_embed_v11_20260814_${commit:0:12}"
test ! -e "$root"
mkdir -p "$root/prereg" "$root/manifest" "$root/smoke"
exec > >(tee "$root/preflight.log") 2>&1

printf 'PREFLIGHT_01_ARTIFACT_SIDE_KNOBS commit=%s\n' "$commit"
printf '%s\n' "$commit" > "$root/prereg/expected_commit.txt"
printf '%s\n' "$cards_sha" > "$root/prereg/cards_sha256.txt"
printf '%s\n' "$pairs_sha" > "$root/prereg/train_pairs_sha256.txt"
printf '%s\n' "$run_map_sha" > "$root/prereg/run_map_sha256.txt"
printf '%s\n' "$split_sha" > "$root/prereg/split_sha256.txt"
printf '%s\n' "$model_sha" > "$root/prereg/model_sha256.txt"
cp phase1/frozen_embed_manifest.py "$root/prereg/"
cp phase1/frozen_embed_worker.py "$root/prereg/"
cp phase1/frozen_embed_rank.py "$root/prereg/"
cp phase1/verify_frozen_embed_discovery.py "$root/prereg/"
cp phase1/frozen_embed_split_audit.py "$root/prereg/"
cp phase1/check_frozen_embed_smoke.py "$root/prereg/"
cp phase1/frozen_embed_smoke_20260814.sbatch "$root/prereg/"
cp phase1/frozen_embed_full_20260814.sbatch "$root/prereg/"
cp phase1/scripts/watch_frozen_embed_discovery_20260814.sh "$root/prereg/"
cp phase1/实验记录/2026-08-14/Frozen05B8192_RunOOF发现门_预注册.md "$root/prereg/"
cp phase1/实验记录/2026-08-14/Frozen05B8192_RunOOF_长实验预检.md "$root/prereg/"
grep -q -- '--max-len 8192 --head-fraction 0.25 --batch-size 2 --chunk-size 32' \
  phase1/frozen_embed_full_20260814.sbatch
grep -q 'C=0.05' phase1/实验记录/2026-08-14/Frozen05B8192_RunOOF发现门_预注册.md

printf 'PREFLIGHT_02_CHEAP_TESTS\n'
"$py" -m py_compile \
  phase1/frozen_embed_manifest.py \
  phase1/frozen_embed_worker.py \
  phase1/frozen_embed_rank.py \
  phase1/verify_frozen_embed_discovery.py \
  phase1/frozen_embed_split_audit.py \
  phase1/check_frozen_embed_smoke.py
"$py" -m pytest -q phase1/tests/test_frozen_embed_pipeline.py

printf 'PREFLIGHT_03_TRAIN_PAIR_DEDUP_AND_MANIFEST\n'
printf '%s  %s\n' \
  "$cards_sha" "$cards" \
  "$pairs_sha" "$pairs" \
  "$run_map_sha" "$run_map" \
  "$split_sha" "$split" \
  "$model_sha" "$model/model.safetensors" \
  | sha256sum --check --strict
if head -1 "$cards" | grep -Fq 'version https://git-lfs.github.com/spec/v1'; then
  echo FROZEN_EMBED_ABORT_CARDS_IS_LFS_POINTER >&2
  exit 2
fi
test "$(wc -l < "$cards" | tr -d '[:space:]')" = 16012
test "$(wc -l < "$pairs" | tr -d '[:space:]')" = 4263
"$py" phase1/frozen_embed_manifest.py \
  --cards "$cards" --pairs "$pairs" --run-map "$run_map" \
  --expected-split train --num-shards 4 \
  --out-manifest "$root/manifest/train_endpoints.jsonl" \
  --out-summary "$root/manifest/train_endpoints_summary.json" \
  --expect-cards-sha256 "$cards_sha" \
  --expect-pairs-sha256 "$pairs_sha" \
  --expect-run-map-sha256 "$run_map_sha"
"$py" phase1/frozen_embed_manifest.py \
  --cards "$cards" --pairs "$pairs" --run-map "$run_map" \
  --expected-split train --num-shards 4 \
  --out-manifest "$root/manifest/train_endpoints.rebuild.jsonl" \
  --out-summary "$root/manifest/train_endpoints_summary.rebuild.json" \
  --expect-cards-sha256 "$cards_sha" \
  --expect-pairs-sha256 "$pairs_sha" \
  --expect-run-map-sha256 "$run_map_sha"
cmp "$root/manifest/train_endpoints.jsonl" "$root/manifest/train_endpoints.rebuild.jsonl"
manifest_sha=$(sha256sum "$root/manifest/train_endpoints.jsonl" | awk '{print $1}')
test "$manifest_sha" = "$(jq -r '.outputs.manifest_sha256' "$root/manifest/train_endpoints_summary.json")"
test "$manifest_sha" = "$(jq -r '.outputs.manifest_sha256' "$root/manifest/train_endpoints_summary.rebuild.json")"
printf '%s\n' "$manifest_sha" > "$root/prereg/manifest_sha256.txt"

printf 'PREFLIGHT_04_DISTRIBUTION_AND_05_EVAL_BALANCE\n'
jq '{pairs,endpoints,runs,tasks,dominant_task,dominant_task_share,per_shard,per_task}' \
  "$root/manifest/train_endpoints_summary.json"
test "$(jq -r '.pairs' "$root/manifest/train_endpoints_summary.json")" = 4263
test "$(jq -r '.endpoints' "$root/manifest/train_endpoints_summary.json")" = 5499
test "$(jq -r '.runs' "$root/manifest/train_endpoints_summary.json")" = 333
test "$(jq -r '.tasks' "$root/manifest/train_endpoints_summary.json")" = 23
jq -e '.dominant_task_share <= 0.25' "$root/manifest/train_endpoints_summary.json" >/dev/null
grep -q 'GroupKFold' phase1/frozen_embed_rank.py
grep -q 'equal_total_weight_per_parent' phase1/frozen_embed_rank.py
grep -q 'task_macro_ci95' phase1/frozen_embed_rank.py
grep -q 'truncated_share' phase1/frozen_embed_rank.py

printf 'PREFLIGHT_06_CHECKPOINT_AND_PROVENANCE\n'
test -f "$model/model.safetensors"
"$py" - "$model/config.json" <<'PY'
import json, sys
config=json.load(open(sys.argv[1], encoding="utf-8"))
assert config["hidden_size"] == 896
assert config["max_position_embeddings"] >= 8192
print("MODEL_CONFIG_PASS", config["hidden_size"], config["max_position_embeddings"])
PY
grep -q 'np.savez_compressed' phase1/frozen_embed_worker.py
grep -q 'os.replace' phase1/frozen_embed_worker.py
grep -q 'FROZEN_EMBED_WORKER_ALREADY_COMPLETE' phase1/frozen_embed_worker.py

printf 'PREFLIGHT_07_RUN_NODE_CODE_LEAKAGE\n'
"$py" phase1/frozen_embed_split_audit.py \
  --cards "$cards" \
  --manifest "$root/manifest/train_endpoints.jsonl" \
  --split "$split" \
  --out "$root/manifest/train_held_isolation.json" \
  --expect-cards-sha256 "$cards_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-split-sha256 "$split_sha"
jq -e '.run_overlap == 0 and .node_overlap == 0 and .raw_code_hash_overlap == 0 and .frozen_pair_file_opened == false' \
  "$root/manifest/train_held_isolation.json" >/dev/null
test "$(grep -Ec 'decision_frozen|decision_clean_b' phase1/frozen_embed_manifest.py phase1/frozen_embed_worker.py phase1/frozen_embed_rank.py || true)" = 0

printf 'PREFLIGHT_08_RNG_AND_SPLIT_FREEZE\n'
test "$(jq -r '.seed' "$root/manifest/train_endpoints_summary.json")" = 887
test "$(jq -r '.seed' "$split")" = 7
test "$(jq -r '.prior_hold_runs == .prior_hold_survived' "$root/manifest/train_held_isolation.json")" = true
test "$(jq -sr '[.[].shard]|min' "$root/manifest/train_endpoints.jsonl")" = 0
test "$(jq -sr '[.[].shard]|max' "$root/manifest/train_endpoints.jsonl")" = 3

printf 'PREFLIGHT_09_SECRET_SCAN\n'
filename_secret_count=$(git show --pretty='' --name-only HEAD | grep -icE 'env|key|token|secret' || true)
content_secret_count=$(
  {
    git show --format= --no-ext-diff HEAD
    cat "$root/manifest/train_endpoints.jsonl"
  } | grep -Ec 'sk-(ws-)?[A-Za-z0-9._-]{24,}|AKIA[0-9A-Z]{16}' || true
)
printf 'COMMIT_FILENAME_SECRET_COUNT=%s CONTENT_SECRET_COUNT=%s\n' \
  "$filename_secret_count" "$content_secret_count"
test "$filename_secret_count" -eq 0
test "$content_secret_count" -eq 0

printf 'PREFLIGHT_10_WALLCLOCK_AND_CLUSTER\n'
test "$(grep -c '^#SBATCH --time=00:15:00$' phase1/frozen_embed_smoke_20260814.sbatch)" = 1
test "$(grep -c '^#SBATCH --time=04:00:00$' phase1/frozen_embed_full_20260814.sbatch)" = 1
test "$(grep -c '^#SBATCH --array=0-3%4$' phase1/frozen_embed_full_20260814.sbatch)" = 1
for script in phase1/frozen_embed_smoke_20260814.sbatch phase1/frozen_embed_full_20260814.sbatch; do
  test "$(grep -c '^#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38$' "$script")" = 1
  test "$(grep -c '^#SBATCH --constraint=rtx3090$' "$script")" = 1
  test "$(grep -c '^#SBATCH --gres=gpu:1$' "$script")" = 1
done
active_jobs=$(squeue -h -u yzyang4 | wc -l)
printf 'ACTIVE_JOB_ROWS_BEFORE_SMOKE=%s\n' "$active_jobs"
test "$active_jobs" -le 3

printf 'PREFLIGHT_11_TRAINING_POWER_12_RC_13_APPEND_ONLY\n'
test "$(jq -r '.pairs' "$root/manifest/train_endpoints_summary.json")" -ge 4000
test "$(jq -r '.runs' "$root/manifest/train_endpoints_summary.json")" -ge 300
test "$(grep -c 'worker_rc=\$?' phase1/frozen_embed_smoke_20260814.sbatch)" = 1
test "$(grep -c 'worker_rc=\$?' phase1/frozen_embed_full_20260814.sbatch)" = 1
grep -q 'rank_rc=\$?' phase1/scripts/watch_frozen_embed_discovery_20260814.sh
grep -q 'verify_rc=\$?' phase1/scripts/watch_frozen_embed_discovery_20260814.sh
jq -e '.prior_hold_runs == 145 and .prior_hold_survived == 145 and .hold_runs == 156' \
  "$root/manifest/train_held_isolation.json" >/dev/null

find "$root/prereg" -maxdepth 1 -type f ! -name frozen_file_sha256.txt -print0 \
  | sort -z | xargs -0 sha256sum > "$root/prereg/frozen_file_sha256.txt"
test -z "$(git status --short)"
printf 'ALL_FROZEN_EMBED_PREFLIGHT_GATES_PASS_SUBMITTING_SMOKE\n'
smoke_job=$(sbatch --parsable \
  --export="ALL,EXPERIMENT_ROOT=$root,EXPECTED_COMMIT=$commit,EXPECTED_MANIFEST_SHA=$manifest_sha,EXPECTED_CARDS_SHA=$cards_sha,EXPECTED_MODEL_SHA=$model_sha" \
  phase1/frozen_embed_smoke_20260814.sbatch)
printf '%s\n' "$smoke_job" > "$root/smoke_job_id.txt"
nohup bash phase1/scripts/watch_frozen_embed_discovery_20260814.sh "$root" "$smoke_job" \
  > "$root/watcher.log" 2>&1 &
watcher_pid=$!
printf '%s\n' "$watcher_pid" > "$root/watcher_pid.txt"
printf 'FROZEN_EMBED_SMOKE_SUBMITTED job=%s watcher_pid=%s root=%s manifest_sha=%s\n' \
  "$smoke_job" "$watcher_pid" "$root" "$manifest_sha"
