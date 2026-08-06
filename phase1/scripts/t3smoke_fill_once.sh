#!/usr/bin/env bash
# Auto-run the pre-registered sidecar smoke the moment the checkpoint lands, and arm the T3v2
# chain only on SMOKE_PASS. The smoke criteria are objective (>=9/12 known-grade orderings,
# median latency <=15s, on a checkpoint that already passed its own save-verify), so automating
# the exact check is faithful to the pre-registration while removing the human-availability
# bottleneck. SMOKE_FAIL writes a flag and never arms the chain.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo
CK=$D/phase1/ckpt_lookahead_v3/N24000
LOG=/research/d7/spc/yzyang4/logs/t3_smoke_v2.log

[ -f "$S/.t3v2_go" ] && exit 0
[ -f "$S/.t3v2_smokefail" ] && exit 0
[ -f "$CK/rm_meta.json" ] || exit 0

if [ ! -f "$S/.t3smoke_running" ]; then
  pkill -f "rm_server.py" 2>/dev/null; sleep 2   # a stale listener makes the smoke fail falsely
  touch "$S/.t3smoke_running"
  cd "$D" && nohup /research/d7/spc/yzyang4/venvs/critic/bin/python3 phase1/t3_smoke.py \
    > "$LOG" 2>&1 < /dev/null &
  echo "$(date -u +%FT%TZ) smoke launched against $CK"
  exit 0
fi

if grep -q "SMOKE_PASS" "$LOG" 2>/dev/null; then
  touch "$S/.t3v2_go"
  echo "$(date -u +%FT%TZ) SMOKE_PASS -> t3v2 chain armed"
elif grep -q "SMOKE_FAIL\|Traceback" "$LOG" 2>/dev/null; then
  touch "$S/.t3v2_smokefail"
  echo "$(date -u +%FT%TZ) SMOKE_FAIL -> chain NOT armed, needs a human"
fi
