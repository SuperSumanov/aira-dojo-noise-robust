#!/usr/bin/env bash
# Freeze and submit the six-task public-only warm smoke (6 candidates, 0 API).
set -eo pipefail
if [[ -f "${HOME}/env_setup.sh" ]]; then source "${HOME}/env_setup.sh"; fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 4 ]]; then
  echo "usage: $0 SOURCE_ROOT DATA_GATE PREPARATION RUN_ROOT" >&2
  exit 2
fi
source_root="$1"
data_gate="$2"
preparation="$3"
run_root="$4"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
container=/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif
if [[ -e "$run_root" || -L "$run_root" ]]; then
  echo "E2-A warm-smoke run root must be new" >&2
  exit 2
fi
for path in "$source_root" "$data_gate" "$preparation" "$python_bin" "$container"; do
  if [[ ! -e "$path" ]]; then echo "missing required path: $path" >&2; exit 2; fi
done
expected_commit="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["source_commit"])' "$preparation/real_contract.json")"
test "$(git -C "$source_root" -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false rev-parse HEAD)" = "$expected_commit"
test -z "$(git -C "$source_root" -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false status --porcelain)"

mkdir -m 0700 "$run_root"
mkdir -m 0700 \
  "$run_root/outputs" "$run_root/workspaces" "$run_root/receipts" \
  "$run_root/logs" "$run_root/job_rc" "$run_root/nvfix" \
  "$run_root/capability" "$run_root/slurm"
cp "$source_root/phase1/balanced_continuation_e2a_warm_smoke_20260819.sbatch" \
  "$run_root/job.sbatch"
cp "$source_root/phase1/scripts/monitor_balanced_continuation_e2a_warm_smoke_20260819.sh" \
  "$run_root/monitor.sh"
chmod 0500 "$run_root/job.sbatch" "$run_root/monitor.sh"
printf '%s\n' "$expected_commit" >"$run_root/source_commit.txt"
printf '%s\n' "$data_gate" >"$run_root/data_gate_root.txt"
printf '%s\n' "$preparation" >"$run_root/preparation_root.txt"

cd "$source_root"
hf_cache="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["hf_cache_path"])' "$preparation/real_contract.json")"
hf_manifest_sha="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["hf_cache_manifest_sha256"])' "$preparation/real_contract.json")"
hf_payload_sha="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["hf_cache_payload_sha256"])' "$preparation/real_contract.json")"
"$python_bin" -m phase1.verify_e2a_hf_cache \
  --cache "$hf_cache" \
  --expected-manifest-sha256 "$hf_manifest_sha" \
  --expected-payload-sha256 "$hf_payload_sha" \
  --receipt "$run_root/hf_cache.independent.verify.json" \
  >"$run_root/logs/hf_cache_verify.stdout" \
  2>"$run_root/logs/hf_cache_verify.stderr"

set +e
"$python_bin" -m pytest -q phase1/tests \
  >"$run_root/logs/linux_phase1_tests.stdout" \
  2>"$run_root/logs/linux_phase1_tests.stderr"
tests_rc=$?
set -e
printf '%s\n' "$tests_rc" >"$run_root/linux_phase1_tests.rc"
if [[ "$tests_rc" != 0 ]]; then
  echo "E2-A warm-smoke full Linux test gate failed" >&2
  exit "$tests_rc"
fi

"$python_bin" -m phase1.verify_balanced_continuation_e2a_manifest \
  --result "$preparation/assignment" \
  --receipt "$run_root/assignment.verify.json" \
  >"$run_root/logs/assignment_verify.stdout" \
  2>"$run_root/logs/assignment_verify.stderr"

"$python_bin" -c 'import json,sys; p=json.load(open(sys.argv[1])); req={"rollout_jobs":60,"candidate_executions":120,"operator_api_calls":60,"expected_gpu_hours":13.581222464241607,"candidate_timeout_upper_bound_gpu_hours":40.0,"warm_smoke_candidate_executions":6,"warm_smoke_operator_api_calls":0,"warm_smoke_hard_gpu_hours":2.0,"slurm_array_concurrency":4,"slurm_max_submitted_tasks":4,"warm_smoke_submission_chunks":2,"formal_submission_chunks":15,"qos_chunk_policy":"sequential_nonadaptive_max4","gpus_per_job":1,"formal_submission_requires_passing_warm_smoke":True}; assert all(p.get(k)==v for k,v in req.items()); assert len(p["warm_smoke_assignment_indices"])==len(set(p["warm_smoke_assignment_indices"]))==6; json.dump({"status":"E2A_WARM_SMOKE_MATRIX_VERIFIED","matrix":req,"indices":p["warm_smoke_assignment_indices"]},open(sys.argv[2],"w"),sort_keys=True,separators=(",",":")); open(sys.argv[2],"a").write("\n")' \
  "$preparation/run_plan.json" "$run_root/resource_matrix.verify.json"

printf '%s\n' \
  'PASS 1: tested knob is six-task public-only warm execution; outputs bind task/index/code/contract hashes.' \
  'PASS 2: full Linux phase1/tests and independent variable-K assignment reconstruction passed before submission.' \
  'PASS 3: no train/test learner exists in this engineering smoke; frozen official/future evaluation sets are not read.' \
  'PASS 4: task balance is exactly one frozen candidate for each of six tasks; no result is interpreted scientifically.' \
  'PASS 5: no model evaluation sampling or length heuristic is used; all six fixed tasks must pass.' \
  'PASS 6: no model is trained; save-adapter is not applicable.' \
  'PASS 7: selected anchors already passed pair/node/code-hash zero-overlap gates against frozen and prior runs.' \
  'PASS 8: the six smoke indices and all formal assignment seeds are hash-derived and frozen.' \
  'PASS 9: no credential file is sourced; candidate env is allowlisted; filename/content scans are per job.' \
  'PASS 10: 6 candidate executions x 1200 seconds gives a 2 GPU-hour candidate hard cap; Slurm wall is 35 minutes/job.' \
  'PASS 11: this is an engineering gate with zero scientific power claim and zero API calls.' \
  'PASS 12: every capability/producer/verifier/safety rc is stored before exit; any nonzero rc stops formal launch.' \
  'PASS 13: source, task, anchor, sibling, code, split and full read-only HF cache payload are hash-frozen.' \
  >"$run_root/preflight_13_of_13.txt"

filename_hits="$(find "$preparation" "$run_root/assignment.verify.json" \
  "$run_root/resource_matrix.verify.json" "$run_root/preflight_13_of_13.txt" \
  "$run_root/hf_cache.independent.verify.json" \
  -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$preparation" "$run_root/assignment.verify.json" \
  "$run_root/resource_matrix.verify.json" "$run_root/preflight_13_of_13.txt" \
  "$run_root/hf_cache.independent.verify.json" | wc -l || true)"
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' \
  "$filename_hits" "$content_hits" >"$run_root/preflight_secret_scan.txt"
if [[ "$filename_hits" != 0 || "$content_hits" != 0 ]]; then
  echo "E2-A warm-smoke preflight secret scan failed" >&2
  exit 7
fi

printf '{"status":"E2A_WARM_SMOKE_QOS_MONITOR_PENDING","chunks":["0,1,2,3","4,5"],"max_submitted_tasks":4,"candidate_executions":6,"api_calls":0,"candidate_hard_gpu_hours":2.0}\n' \
  >"$run_root/submission.pending.json"
nohup bash "$run_root/monitor.sh" "$source_root" "$preparation" "$run_root" \
  >"$run_root/logs/monitor.stdout" 2>"$run_root/logs/monitor.stderr" </dev/null &
monitor_pid="$!"
printf '%s\n' "$monitor_pid" >"$run_root/monitor.pid"
printf 'STATUS=E2A_WARM_SMOKE_QOS_MONITOR_STARTED\nMONITOR_PID=%s\nRUN_ROOT=%s\n' \
  "$monitor_pid" "$run_root"
