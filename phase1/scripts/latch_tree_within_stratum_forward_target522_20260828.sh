#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 4 ]]; then
  echo 'usage: latch_tree_within_stratum_forward_target522_20260828.sh {start|resume} OUTPUT_ROOT SOURCE_COMMIT PROTOCOL_SHA256' >&2
  exit 64
fi
readonly mode=$1
readonly root=$2
readonly source_commit=$3
readonly protocol_sha=$4
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly state_root=/research/d7/spc/yzyang4/prospective_decision_v1
readonly protocol_path=phase1/tree_linearization_within_stratum_forward_target522_v2.json
readonly script_path=phase1/scripts/latch_tree_within_stratum_forward_target522_20260828.sh
readonly baseline=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly baseline_runs=435
readonly target_runs=522
readonly minimum_increment_runs=87
readonly stable_polls_required=6
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

[[ $mode == start || $mode == resume ]]
[[ $root =~ ^/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-[A-Za-z0-9._-]+$ ]]
[[ $source_commit =~ ^[0-9a-f]{40}$ ]]
[[ $protocol_sha =~ ^[0-9a-f]{64}$ ]]

snapshot_fields() {
  local snapshot=$1 output=$2 snapshot_root summary registry runs summary_sha registry_sha runs_sha
  snapshot_root=${state_root}/snapshots/${snapshot}
  summary=${snapshot_root}/accumulator/summary.json
  registry=${snapshot_root}/intake_registry.jsonl
  runs=${snapshot_root}/accumulator/provisional_runs.jsonl
  test -d "$snapshot_root" && test ! -L "$snapshot_root"
  for path in "$summary" "$registry" "$runs"; do
    test -f "$path" && test ! -L "$path"
  done
  summary_sha=$(sha256sum "$summary" | awk '{print $1}')
  registry_sha=$(sha256sum "$registry" | awk '{print $1}')
  runs_sha=$(sha256sum "$runs" | awk '{print $1}')
  jq -e --arg registry_sha "$registry_sha" --arg runs_sha "$runs_sha" '
    .protocol == "prospective_accumulator_v1"
    and .closure.provided == false
    and .security.label_vault_opened == false
    and .security.outcome_files_opened == []
    and .security.scorer_prediction_files_opened == []
    and .inputs.registry_sha256 == $registry_sha
    and .outputs.provisional_runs_sha256 == $runs_sha
    and (.inventory.provisional_first960_runs | type) == "number"
    and .inventory.provisional_first960_runs == (.inventory.provisional_first960_runs | floor)
    and .inventory.provisional_first960_runs > 0
    and (.inventory.provisional_first960_endpoints | type) == "number"
    and .inventory.provisional_first960_endpoints == (.inventory.provisional_first960_endpoints | floor)
    and .inventory.provisional_first960_endpoints > 0
    and (.task_support.provisional_first960.tasks | type) == "number"
    and .task_support.provisional_first960.tasks == (.task_support.provisional_first960.tasks | floor)
    and .task_support.provisional_first960.tasks > 0
  ' "$summary" >/dev/null
  jq -r --arg snapshot "$snapshot" --arg summary_sha "$summary_sha" \
    --arg registry_sha "$registry_sha" --arg runs_sha "$runs_sha" '
    [
      $snapshot,
      (.inventory.provisional_first960_runs | tostring),
      (.inventory.provisional_first960_endpoints | tostring),
      (.task_support.provisional_first960.tasks | tostring),
      $summary_sha,
      $registry_sha,
      $runs_sha
    ] | @tsv
  ' "$summary" >"$output"
}

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${source_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$source_commit" fork/phase1-value-critic

if [[ $mode == start ]]; then
  test ! -e "$root"
  mkdir -p "$root"
else
  test -d "$root" && test ! -L "$root"
  test ! -e "$root/COMPLETE"
  test ! -e "$root/FAILED_RC"
  test ! -e "$root/CONTINUITY_GAP"
fi

exec 9>"$root/monitor.lock"
flock -n 9
printf '%s\n' "$$" >"$root/monitor.pid"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "$rc" >"$root/FAILED_RC" 2>/dev/null || true; fi; exit "$rc"' EXIT

if [[ $mode == start ]]; then
  git -C "$repo" show "${source_commit}:${protocol_path}" >"$root/protocol.json"
  git -C "$repo" show "${source_commit}:${script_path}" >"$root/source_script.sh"
  test "$(sha256sum "$root/protocol.json" | awk '{print $1}')" = "$protocol_sha"
  cmp "$root/source_script.sh" "$0"
  latest=$(tr -d '\r\n' <"$state_root/LATEST")
  test "$latest" = "$baseline"
  snapshot_fields "$baseline" "$root/current.tsv.tmp"
  IFS=$'\t' read -r observed observed_runs observed_endpoints observed_tasks observed_summary_sha observed_registry_sha observed_runs_sha <"$root/current.tsv.tmp"
  test "$observed" = "$baseline"
  test "$observed_runs" = "$baseline_runs"
  printf 'snapshot_sha256\truns\tendpoints\ttasks\tsummary_sha256\tregistry_sha256\truns_sha256\tobserved_at_utc\n' >"$root/observed.tsv"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$observed" "$observed_runs" "$observed_endpoints" "$observed_tasks" \
    "$observed_summary_sha" "$observed_registry_sha" "$observed_runs_sha" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$root/observed.tsv"
  rm "$root/current.tsv.tmp"
  cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_question=atomically select first observed Target-522 snapshot for a disjoint forward-run structural confirmation; PASS
03_source_commit=${source_commit}; PASS
04_protocol_sha256=${protocol_sha}; PASS
05_initial_latest=${baseline},initial runs=${baseline_runs}; PASS
06_target=first observed runs at least ${target_runs},boundary overshoot retained,manual choice false; PASS
07_primary_population=candidate physical runs absent from baseline,minimum increment ${minimum_increment_runs}; PASS
08_selection_inputs=LATEST plus outcome-blind accumulator counts and hashes only,no profile values; PASS
09_stability=${stable_polls_required} consecutive candidate hash checks before READY; PASS
10_checkpoint=journaled observations; resume only if LATEST still equals last observation; PASS
11_forbidden=no label,outcome,prediction,accuracy,effect,utility,raw archive read; PASS
12_resources=CPU monitor only,GPU/API/model-fit/base-update 0/0/0/0; PASS
13_failure=gap,regression,hash drift,credential,duplicate or monitor error fails closed; PASS
EOF
else
  test -f "$root/protocol.json" && test -f "$root/source_script.sh" && test -f "$root/observed.tsv"
  test "$(sha256sum "$root/protocol.json" | awk '{print $1}')" = "$protocol_sha"
  cmp "$root/source_script.sh" "$0"
  awk -F '\t' '
    NR == 1 {
      if ($0 != "snapshot_sha256\truns\tendpoints\ttasks\tsummary_sha256\tregistry_sha256\truns_sha256\tobserved_at_utc") exit 1
      next
    }
    {
      if (length($1) != 64 || $1 ~ /[^0-9a-f]/ || $2 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ || $4 !~ /^[0-9]+$/) exit 1
      if (seen[$1]++ || (count > 0 && $2 < previous_runs)) exit 1
      previous_runs=$2
      count++
    }
    END {if (count < 1) exit 1}
  ' "$root/observed.tsv"
  last_observed=$(tail -n 1 "$root/observed.tsv" | cut -f1)
  latest=$(tr -d '\r\n' <"$state_root/LATEST")
  if test "$latest" != "$last_observed"; then
    printf 'status=CONTINUITY_GAP_FAIL_CLOSED\nlast_observed=%s\ncurrent_latest=%s\n' \
      "$last_observed" "$latest" >"$root/CONTINUITY_GAP"
    exit 3
  fi
  rm -f "$root/TIMEOUT_RC"
fi

candidate=
stable_polls=0
if test -f "$root/candidate.tsv"; then
  awk -F '\t' '
    NR != 1 {exit 1}
    NF != 7 {exit 1}
    length($1) != 64 || $1 ~ /[^0-9a-f]/ {exit 1}
    $2 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ || $4 !~ /^[0-9]+$/ {exit 1}
    length($5) != 64 || $5 ~ /[^0-9a-f]/ {exit 1}
    length($6) != 64 || $6 ~ /[^0-9a-f]/ {exit 1}
    length($7) != 64 || $7 ~ /[^0-9a-f]/ {exit 1}
  ' "$root/candidate.tsv"
  IFS=$'\t' read -r candidate candidate_runs candidate_endpoints candidate_tasks candidate_summary_sha candidate_registry_sha candidate_runs_sha <"$root/candidate.tsv"
  test "$candidate_runs" -ge "$target_runs"
  test "$((candidate_runs - baseline_runs))" -ge "$minimum_increment_runs"
  candidate_record=$(cat "$root/candidate.tsv")
  awk -F '\t' -v candidate="$candidate" -v candidate_record="$candidate_record" -v target="$target_runs" '
    NR == 1 {next}
    {
      record=$1
      for (field=2; field<=7; field++) record=record "\t" $field
      if (!found && $2 >= target && $1 != candidate) exit 1
      if ($1 == candidate) {
        if (found || record != candidate_record || $2 < target) exit 1
        found=1
      }
    }
    END {if (found != 1) exit 1}
  ' "$root/observed.tsv"
else
  awk -F '\t' -v target="$target_runs" 'NR > 1 && $2 >= target {exit 1}' "$root/observed.tsv"
fi
last_snapshot=$(tail -n 1 "$root/observed.tsv" | cut -f1)
last_runs=$(tail -n 1 "$root/observed.tsv" | cut -f2)

for poll in $(seq 0 51840); do
  latest=$(tr -d '\r\n' <"$state_root/LATEST")
  [[ $latest =~ ^[0-9a-f]{64}$ ]]
  if test "$latest" != "$last_snapshot"; then
    snapshot_fields "$latest" "$root/current.tsv.tmp"
    IFS=$'\t' read -r observed observed_runs observed_endpoints observed_tasks observed_summary_sha observed_registry_sha observed_runs_sha <"$root/current.tsv.tmp"
    test "$observed" = "$latest"
    test "$observed_runs" -ge "$last_runs"
    if test -z "$candidate" && test "$observed_runs" -ge "$target_runs"; then
      awk -F '\t' -v target="$target_runs" 'NR == 1 {next} $2 >= target {exit 1}' "$root/observed.tsv"
      test "$((observed_runs - baseline_runs))" -ge "$minimum_increment_runs"
      cp "$root/current.tsv.tmp" "$root/candidate.tsv.tmp"
      mv "$root/candidate.tsv.tmp" "$root/candidate.tsv"
      candidate=$observed
      stable_polls=0
      printf '%s candidate_latched poll=%s snapshot=%s runs=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" "$candidate" "$observed_runs" >>"$root/monitor.log"
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$observed" "$observed_runs" "$observed_endpoints" "$observed_tasks" \
      "$observed_summary_sha" "$observed_registry_sha" "$observed_runs_sha" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$root/observed.tsv"
    rm "$root/current.tsv.tmp"
    last_snapshot=$observed
    last_runs=$observed_runs
  fi

  if test -n "$candidate"; then
    snapshot_fields "$candidate" "$root/candidate_check.tsv.tmp"
    cmp "$root/candidate.tsv" "$root/candidate_check.tsv.tmp"
    rm "$root/candidate_check.tsv.tmp"
    stable_polls=$((stable_polls + 1))
    if test "$stable_polls" -ge "$stable_polls_required"; then
      IFS=$'\t' read -r candidate_snapshot candidate_runs candidate_endpoints candidate_tasks candidate_summary_sha candidate_registry_sha candidate_runs_sha <"$root/candidate.tsv"
      cat >"$root/READY" <<EOF
status=TARGET522_FIRST_OBSERVED_CROSSING_READY
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source_commit=${source_commit}
protocol_sha256=${protocol_sha}
baseline_snapshot_sha256=${baseline}
baseline_runs=${baseline_runs}
candidate_snapshot_sha256=${candidate_snapshot}
candidate_runs=${candidate_runs}
candidate_endpoints=${candidate_endpoints}
candidate_tasks=${candidate_tasks}
disjoint_increment_runs=$((candidate_runs - baseline_runs))
candidate_summary_sha256=${candidate_summary_sha}
candidate_registry_sha256=${candidate_registry_sha}
candidate_runs_sha256=${candidate_runs_sha}
manual_snapshot_choice=false
earlier_observed_target_crossing_skipped=false
profile_values_read_for_selection=false
prospective_outcomes_or_prediction_values_read=false
raw_senior_archives_opened=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
      filename_hits=$(find "$root" -type f -printf '%f\n' | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
      test "$filename_hits" = 0
      credential_files=$(grep -R -E -i -l "$credential_pattern" "$root" --exclude=security_scan_receipt.txt --exclude=SHA256SUMS || true)
      test -z "$credential_files"
      printf '%s\n' 'boundary_aware_credential_file_hits=0' 'credential_filename_hits=0' >"$root/security_scan_receipt.txt"
      (
        cd "$root"
        find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
          | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
        touch COMPLETE
      )
      chmod -R a-w "$root"
      trap - EXIT
      exit 0
    fi
  fi
  printf '%s waiting poll=%s latest=%s runs=%s candidate=%s stable=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" "$latest" "$last_runs" "${candidate:-none}" "$stable_polls" >>"$root/monitor.log"
  sleep 5
done

printf '%s\n' 124 >"$root/TIMEOUT_RC"
trap - EXIT
exit 0
