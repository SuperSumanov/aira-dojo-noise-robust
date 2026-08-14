#!/usr/bin/env bash
# Read-only cluster audit for the approved balanced-continuation E1 gate.
set -eo pipefail

if [[ -f "${HOME}/env_setup.sh" ]]; then
  # The cluster helper is not nounset-safe.
  source "${HOME}/env_setup.sh"
fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

repo=/research/d7/spc/yzyang4/aira-dojo
cards="${repo}/phase1/cards_current_v11.jsonl"
data_root=/research/d7/spc/yzyang4/mle-bench-data
sif="${repo}/build/superimage/superimage.root.2026-07-macos-v1.sif"
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

printf 'AUDIT_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'HOST=%s\n' "$(hostname)"
printf 'USER=%s\n' "$(id -un)"
printf 'REPO_HEAD=%s\n' "$(git -C "$repo" rev-parse HEAD)"
printf 'REPO_BRANCH=%s\n' "$(git -C "$repo" branch --show-current)"
printf 'REPO_STATUS_BEGIN\n'
git -C "$repo" status --short --branch
printf 'REPO_STATUS_END\n'

printf 'SLURM_QUEUE_BEGIN\n'
squeue -u yzyang4 -o '%.18i %.12P %.24j %.2t %.10M %.4D %R'
printf 'SLURM_QUEUE_END\n'

for required in "$cards" "$sif" "$python_bin"; do
  if [[ ! -f "$required" ]]; then
    printf 'REQUIRED_MISSING=%s\n' "$required"
    exit 3
  fi
done
printf 'CARDS_ROWS=%s\n' "$(wc -l < "$cards")"
printf 'CARDS_BYTES=%s\n' "$(stat -c %s "$cards")"
printf 'CARDS_SHA256=%s\n' "$(sha256sum "$cards" | awk '{print $1}')"
printf 'SIF_SHA256=%s\n' "$(sha256sum "$sif" | awk '{print $1}')"
printf 'PYTHON_VERSION=%s\n' "$("$python_bin" --version 2>&1)"
printf 'GIT_LFS_PATH=%s\n' "$(command -v git-lfs || true)"

for task in spaceship-titanic tabular-playground-series-may-2022; do
  task_root="${data_root}/${task}/prepared/public"
  if [[ ! -d "$task_root" ]]; then
    printf 'TASK_PUBLIC_MISSING=%s\n' "$task"
    exit 4
  fi
  printf 'TASK_PUBLIC_BEGIN=%s\n' "$task"
  find "$task_root" -maxdepth 2 -type f -printf '%P\t%s\n' | LC_ALL=C sort
  printf 'TASK_PUBLIC_END=%s\n' "$task"
done

"$python_bin" - "$data_root" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
tasks = ("spaceship-titanic", "tabular-playground-series-may-2022")
for task in tasks:
    public = root / task / "prepared" / "public"
    train = public / "train.csv"
    if not train.is_file():
        raise SystemExit(f"TRAIN_CSV_MISSING={task}")
    with train.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = sum(1 for _ in reader)
    # Metadata only: no row values and no private/official-test file is opened.
    print("TRAIN_METADATA=" + json.dumps({
        "task": task,
        "rows": rows,
        "columns": header,
        "bytes": train.stat().st_size,
    }, sort_keys=True, separators=(",", ":")))
PY

printf 'REMOTE_E1_STATE_AUDIT_PASS\n'
