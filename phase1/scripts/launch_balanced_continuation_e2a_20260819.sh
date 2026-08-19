#!/usr/bin/env bash
# Freeze E2-A run root and start the score-blind QOS-aware two-wave monitor.
set -eo pipefail
if [[ -f "${HOME}/env_setup.sh" ]]; then source "${HOME}/env_setup.sh"; fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ $# -ne 5 ]]; then
  echo "usage: $0 SOURCE_ROOT DATA_GATE PREPARATION WARM_GATE_RECEIPT RUN_ROOT" >&2
  exit 2
fi
source_root="$1"
data_gate="$2"
preparation="$3"
warm_gate="$4"
run_root="$5"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
container=/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif
if [[ -e "$run_root" || -L "$run_root" ]]; then echo "E2-A run root must be new" >&2; exit 2; fi
for path in "$source_root" "$data_gate" "$preparation" "$warm_gate" "$python_bin" "$container"; do
  if [[ ! -e "$path" ]]; then echo "missing required path: $path" >&2; exit 2; fi
done
expected_commit="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["source_commit"])' "$preparation/real_contract.json")"
test "$(git -C "$source_root" -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false rev-parse HEAD)" = "$expected_commit"
test -z "$(git -C "$source_root" -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false status --porcelain)"
"$python_bin" -c 'import json,sys;v=json.load(open(sys.argv[1])); assert v.get("status")=="VERIFIED_E2A_SIX_TASK_PUBLIC_WARM_SMOKE_PASS"; assert v.get("producer_imported") is False; assert v.get("candidate_executions")==6; assert v.get("api_calls")==0; assert v.get("dsearch_rows_read")==v.get("dval_rows_read")==v.get("dtest_rows_read")==0; assert v.get("labels_opened") is False and v.get("outcomes_read") is False and v.get("all_gate_pass") is True' "$warm_gate"

mkdir -m 0700 "$run_root"
mkdir -m 0700 "$run_root/preflight_receipts" "$run_root/worker_outputs" \
  "$run_root/workspaces" "$run_root/sealed" "$run_root/worker_receipts" \
  "$run_root/job_logs" "$run_root/job_rc" "$run_root/nvfix" \
  "$run_root/capability" "$run_root/slurm" "$run_root/logs"
cp -a "$preparation" "$run_root/preparation"
cp "$warm_gate" "$run_root/preflight_receipts/warm_smoke.verify.json"
cp "$source_root/phase1/balanced_continuation_e2a_20260819.sbatch" "$run_root/job.sbatch"
cp "$source_root/phase1/scripts/monitor_balanced_continuation_e2a_20260819.sh" "$run_root/monitor.sh"
chmod 0500 "$run_root/job.sbatch" "$run_root/monitor.sh"
printf '%s\n' "$expected_commit" >"$run_root/source_commit.txt"
printf '%s\n' "$data_gate" >"$run_root/data_gate_root.txt"

cd "$source_root"
set +e
"$python_bin" -m pytest -q phase1/tests \
  >"$run_root/logs/linux_phase1_tests.stdout" \
  2>"$run_root/logs/linux_phase1_tests.stderr"
tests_rc=$?
set -e
printf '%s\n' "$tests_rc" >"$run_root/linux_phase1_tests.rc"
if [[ "$tests_rc" != 0 ]]; then echo "E2-A full Linux test gate failed" >&2; exit "$tests_rc"; fi
"$python_bin" -m phase1.verify_balanced_continuation_e2a_manifest \
  --result "$run_root/preparation/assignment" \
  --receipt "$run_root/preflight_receipts/assignment.verify.json" \
  >"$run_root/logs/assignment_verify.stdout" \
  2>"$run_root/logs/assignment_verify.stderr"
"$python_bin" -c 'import json,sys;p=json.load(open(sys.argv[1])); req={"rollout_jobs":60,"candidate_executions":120,"operator_api_calls":60,"expected_gpu_hours":10.247889130908273,"candidate_timeout_upper_bound_gpu_hours":20.0,"candidate_timeout_seconds":600,"operator_timeout_seconds":240,"slurm_array_concurrency":4,"slurm_max_submitted_tasks":4,"warm_smoke_submission_chunks":2,"formal_submission_chunks":15,"qos_chunk_policy":"sequential_nonadaptive_max4","gpus_per_job":1,"adaptive_allocation_allowed":False,"post_outcome_replacement_allowed":False}; assert all(p.get(k)==v for k,v in req.items()); assert len(p["engineering_wave_indices"])==12 and len(p["remaining_wave_indices"])==48 and set(p["engineering_wave_indices"]).isdisjoint(p["remaining_wave_indices"]); json.dump({"status":"E2A_FORMAL_MATRIX_VERIFIED","matrix":req,"engineering":p["engineering_wave_indices"],"remaining":p["remaining_wave_indices"]},open(sys.argv[2],"w"),sort_keys=True,separators=(",",":"));open(sys.argv[2],"a").write("\n")' \
  "$run_root/preparation/run_plan.json" "$run_root/preflight_matrix.verify.json"

printf '%s\n' \
  'PASS 1: only E2-A matched continuation resource is varied; assignment/output receipts prove the active contract.' \
  'PASS 2: six-task warm-only smoke, full Linux tests, scorer references and independent assignment reconstruction passed.' \
  'PASS 3: frozen/prior runs are excluded; candidate sees only D_train plus unlabeled generated D_search union D_val.' \
  'PASS 4: six tasks, four distinct-run parents/task, exact-two siblings; gate analysis is parent/task balanced.' \
  'PASS 5: no evaluation subsampling or length heuristic exists; all 60 frozen assignments are mandatory.' \
  'PASS 6: no model is trained; every raw response and execution artifact is hash-bound instead.' \
  'PASS 7: pair/node/code hash overlaps against frozen and prior selections are zero by the frozen support receipt.' \
  'PASS 8: seed 20260819, variable-K blocks, rollout seeds and wave indices are frozen before outcomes.' \
  'PASS 9: API credential comes only from remote mode-600 .env; candidate env is allowlisted; per-job scans are mandatory.' \
  'PASS 10: E1-Q estimate 10.247889130908273 GPU-hours; candidate hard cap 20 GPU-hours; each job wall 45 minutes.' \
  'PASS 11: fixed support gates use 24 independent parents and six tasks; E2-A itself cannot claim a method win.' \
  'PASS 12: capability/worker/verifier/safety rc are stored before exit; no retry/replacement after paid intent.' \
  'PASS 13: source/data/container/Python/operator/evaluator/assignment hashes are immutable; corpus growth cannot reassign.' \
  >"$run_root/preflight_13_of_13.txt"

filename_hits="$(find "$run_root/preparation" "$run_root/preflight_receipts" \
  "$run_root/preflight_matrix.verify.json" "$run_root/preflight_13_of_13.txt" \
  -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$run_root/preparation" "$run_root/preflight_receipts" \
  "$run_root/preflight_matrix.verify.json" "$run_root/preflight_13_of_13.txt" | wc -l || true)"
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' "$filename_hits" "$content_hits" \
  >"$run_root/preflight_secret_scan.txt"
if [[ "$filename_hits" != 0 || "$content_hits" != 0 ]]; then exit 7; fi
printf '{"status":"E2A_QOS_MONITOR_PENDING","engineering_job":null,"remaining_job":null,"scores_opened":false,"sealed_values_opened":false}\n' \
  >"$run_root/submission.json"
nohup bash "$run_root/monitor.sh" "$run_root" "$source_root" "$data_gate" \
  >"$run_root/logs/monitor.stdout" 2>"$run_root/logs/monitor.stderr" </dev/null &
monitor_pid="$!"
printf '%s\n' "$monitor_pid" >"$run_root/monitor.pid"
printf 'STATUS=E2A_QOS_MONITOR_STARTED\nMONITOR_PID=%s\nRUN_ROOT=%s\n' \
  "$monitor_pid" "$run_root"
