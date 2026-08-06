#!/usr/bin/env bash
# Chain the four pre-registered T3v2 rounds overnight. Armed only by .t3v2_go, which is created
# by hand strictly after SMOKE_PASS -- the protocol forbids launching on an unsmoked sidecar.
# A round submits only when no t3v2 jobs are queued and the previous round's eight runs have
# all checkpointed, so control and guided batches stay paired in time.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
R0=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo
[ -f "$S/.t3v2_go" ] || exit 0

squeue -u "$USER" -h -o %j 2>/dev/null | grep -q "^pool_collect" && exit 0

done_round() {
  local r=$1 c g
  c=$(find "$R0/user_yzyang4_issue_mcts_data_t3v2c$r" -name journal.jsonl 2>/dev/null | wc -l)
  g=$(find "$R0/user_yzyang4_issue_mcts_data_t3v2g$r" -name journal.jsonl 2>/dev/null | wc -l)
  # a wall-killed straggler must not deadlock the chain: accept one lost run per arm.
  # the top-of-script queue check already guarantees the round jobs have exited.
  [ "$c" -ge 3 ] && [ "$g" -ge 3 ]
}

for r in 1 2 3 4; do
  ST=$S/.t3v2_round_${r}_submitted
  if [ ! -f "$ST" ]; then
    if [ "$r" -gt 1 ] && ! done_round $((r-1)); then
      exit 0        # previous round still running or incomplete; wait
    fi
    if bash "$S/t3v2_round.sh" "$r" >> /research/d7/spc/yzyang4/logs/t3v2_rounds.log 2>&1; then
      touch "$ST"
      echo "$(date -u +%FT%TZ) t3v2 round $r submitted"
    else
      echo "$(date -u +%FT%TZ) t3v2 round $r blocked (QOS/balance), retry next heartbeat"
    fi
    exit 0
  fi
done
echo "all t3v2 rounds submitted"
