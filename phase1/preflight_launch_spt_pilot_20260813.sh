#!/usr/bin/env bash
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/spt_ops/spt_label_blind_pilot_v1
prereg="$ops/prereg"
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
cards="$repo/phase1/cards_current_v11.jsonl"
split="$repo/phase1/v11_decision/runsplit_holdruns_v11.json"
runtime="$repo/phase1/scoreable_prediction_tap_runtime.py"
manifest="$prereg/pilot_manifest.jsonl"
audit="$prereg/pilot_audit.json"
rebuild_manifest="$prereg/pilot_manifest.rebuild.jsonl"
rebuild_audit="$prereg/pilot_audit.rebuild.json"
sbatch_source="$repo/phase1/spt_pilot_20260813.sbatch"
watcher_source="$repo/phase1/watch_spt_pilot_20260813.sh"

cd "$repo"
test -z "$(git status --short)"
test ! -e "$ops"
mkdir -p "$prereg"
exec > >(tee "$prereg/launch_preflight_20260813.txt") 2>&1

commit=$(git rev-parse HEAD)
printf '%s\n' "$commit" > "$prereg/git_commit.txt"
printf 'PREFLIGHT_01_KNOBS_ON_DISK commit=%s\n' "$commit"
test -f "$repo/phase1/实验记录/2026-08-13/SPT_标签盲机制pilot预注册.md"
test -f "$repo/phase1/实验记录/2026-08-13/SPT_文献防scoop审计.md"
grep -q 'executions=18' "$sbatch_source"
grep -q 'candidate_cap_s=600' "$sbatch_source"

printf 'PREFLIGHT_02_CHEAP_TESTS\n'
"$py" -m py_compile \
  phase1/scoreable_prediction_tap.py \
  phase1/scoreable_prediction_tap_runtime.py \
  phase1/select_spt_pilot.py \
  phase1/spt_replay_worker.py \
  phase1/spt_replay_entry.py \
  phase1/verify_spt_pilot.py
"$py" -m pytest -q phase1/tests/test_scoreable_prediction_tap.py
PYTHONPATH="$repo/src:$repo:$repo/phase1" "$py" -m phase1.spt_replay_worker \
  --runtime-source "$runtime" --self-test
PYTHONPATH="$repo/src:$repo:$repo/phase1" "$py" -m phase1.verify_spt_pilot --self-test
PYTHONPATH="$repo/src:$repo:$repo/phase1" "$py" -m phase1.schema_probe_contract_worker --self-test

printf 'PREFLIGHT_03_LABEL_BLIND_SELECTION_AND_DEDUP\n'
PYTHONPATH="$repo/src:$repo:$repo/phase1" "$py" -m phase1.select_spt_pilot \
  --cards "$cards" --split "$split" --runtime "$runtime" \
  --manifest "$manifest" --audit "$audit"
PYTHONPATH="$repo/src:$repo:$repo/phase1" "$py" -m phase1.select_spt_pilot \
  --cards "$cards" --split "$split" --runtime "$runtime" \
  --manifest "$rebuild_manifest" --audit "$rebuild_audit"
cmp "$manifest" "$rebuild_manifest"
cmp "$audit" "$rebuild_audit"
manifest_sha=$(sha256sum "$manifest" | awk '{print $1}')
printf '%s\n' "$manifest_sha" > "$prereg/manifest_sha256.txt"
PYTHONPATH="$repo/src:$repo:$repo/phase1" "$py" - "$manifest" "$runtime" <<'PY'
import json
import sys
from pathlib import Path
from phase1.spt_replay_worker import file_sha256, load_manifest

manifest = Path(sys.argv[1])
runtime = Path(sys.argv[2])
rows = load_manifest(manifest, file_sha256(runtime))
assert len(rows) == 18
assert len({row["card_id"] for row in rows}) == 6
assert len({row["group_id"] for row in rows}) == 3
assert len({row["competition"] for row in rows}) == 3
assert all("label" not in row and "obs" not in row for row in rows)
print("SPT_ACTUAL_MANIFEST_GRID_PASS")
PY

printf 'PREFLIGHT_04_DISTRIBUTION_AND_05_EVAL_STRATA\n'
jq '{tasks,task_metadata,eligible_groups,census,selected:[.selected[]|{group_index,competition,card_id,tap_site_count,base_code_bytes}]}' "$audit"
grep -q 'semantics' "$repo/phase1/实验记录/2026-08-13/SPT_标签盲机制pilot预注册.md"
grep -q 'feedback gain' "$repo/phase1/实验记录/2026-08-13/SPT_标签盲机制pilot预注册.md"

printf 'PREFLIGHT_06_SAVE_AND_PROVENANCE\n'
cp "$sbatch_source" "$prereg/spt_pilot_20260813.sbatch"
cp "$watcher_source" "$prereg/watch_spt_pilot_20260813.sh"
cp "$repo/phase1/verify_spt_pilot.py" "$prereg/verify_spt_pilot.py"
cp "$repo/phase1/实验记录/2026-08-13/SPT_标签盲机制pilot预注册.md" "$prereg/"
cp "$repo/phase1/实验记录/2026-08-13/SPT_文献防scoop审计.md" "$prereg/"

printf 'PREFLIGHT_07_LEAKAGE\n'
test -d /research/d7/spc/yzyang4/mle-bench-data/random-acts-of-pizza/prepared/public
test -d /research/d7/spc/yzyang4/mle-bench-data/us-patent-phrase-to-phrase-matching/prepared/public
test -d /research/d7/spc/yzyang4/mle-bench-data/petfinder-pawpularity-score/prepared/public
test "$(grep -c 'raw.get("label")\|raw.get("obs")' "$repo/phase1/select_spt_pilot.py" || true)" -eq 0

printf 'PREFLIGHT_08_RNG_ORDER\n'
test "$(jq -r '.seed' "$manifest" | sort -u)" = 20260813
test "$(jq -r '.index' "$manifest" | paste -sd, -)" = 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17

printf 'PREFLIGHT_09_SECRET_SCAN\n'
filename_secret_count=$(git show --pretty='' --name-only HEAD | grep -icE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' || true)
content_secret_count=$(
  {
    git show --format= --no-ext-diff HEAD
    cat "$manifest" "$rebuild_manifest"
  } | grep -Ec 'sk-(ws-)?[A-Za-z0-9._-]{24,}|AKIA[0-9A-Z]{16}' || true
)
printf 'COMMIT_FILENAME_SECRET_COUNT=%s CONTENT_SECRET_COUNT=%s\n' "$filename_secret_count" "$content_secret_count"
test "$filename_secret_count" -eq 0
test "$content_secret_count" -eq 0

printf 'PREFLIGHT_10_WALLTIME_CLUSTER\n'
test "$(grep -c '^#SBATCH --gres=gpu:3$' "$sbatch_source")" -eq 1
test "$(grep -c '^#SBATCH --time=01:30:00$' "$sbatch_source")" -eq 1
test "$(grep -c '^#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38$' "$sbatch_source")" -eq 1
active_jobs=$(squeue -h -u yzyang4 | wc -l)
printf 'ACTIVE_JOB_ROWS=%s\n' "$active_jobs"
test "$active_jobs" -le 3
container_sha=$(sha256sum /research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif | awk '{print $1}')
test "$container_sha" = 801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda

printf 'PREFLIGHT_11_POWER_12_TRUE_RC_13_FREEZE\n'
grep -q 'N=6/3 groups' "$repo/phase1/实验记录/2026-08-13/SPT_标签盲机制pilot预注册.md"
grep -q 'return_code' "$repo/phase1/spt_replay_entry.py"
sha256sum "$prereg/verify_spt_pilot.py" | awk '{print $1}' > "$prereg/independent_verifier_sha256.txt"
find "$prereg" -maxdepth 1 -type f \
  ! -name frozen_file_sha256.txt ! -name launch_preflight_20260813.txt -print0 \
  | sort -z | xargs -0 sha256sum > "$prereg/frozen_file_sha256.txt"
git status --short
test -z "$(git status --short)"

printf 'ALL_SPT_PREFLIGHT_GATES_PASS_SUBMITTING\n'
job_id=$(sbatch --parsable "$prereg/spt_pilot_20260813.sbatch")
printf '%s\n' "$job_id" > "$ops/job_id.txt"
nohup bash "$prereg/watch_spt_pilot_20260813.sh" "$job_id" \
  > "$ops/watcher.nohup.out" 2>&1 &
printf '%s\n' "$!" > "$ops/watcher_pid.txt"
printf 'SPT_PILOT_SUBMITTED job=%s watcher_pid=%s manifest_sha=%s\n' \
  "$job_id" "$(cat "$ops/watcher_pid.txt")" "$manifest_sha"
