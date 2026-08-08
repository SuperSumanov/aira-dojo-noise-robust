"""Add a provider-aware balance guard to pool_fill_once.sh.

Gap found 2026-08-08 while preflighting the Qwen campaign: deep_fill_once.sh and
t3v2_round.sh probe balance before submitting, pool_fill_once.sh does not -- yet it is the
function pool_collect.sbatch calls to chain the NEXT batch. An account that goes dry
mid-chain therefore converts money into nothing, which is exactly how half of gen2VAL was
lost. Provider follows the tag: gen2* -> dashscope (qwen), everything else -> deepseek.

The probe runs AFTER the worklist pick so the tag is known, and before either sbatch.
"""
import io

P = "/research/d7/spc/yzyang4/scripts/pool_fill_once.sh"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

old = 'set -- $next' + NL + 'TS="${4:-}"'
new = ('set -- $next' + NL +
       '# balance guard: refuse to burn a batch the account cannot finish (provider by tag)' + NL +
       'PROV=deepseek; FLOOR=25; case "$3" in gen2*) PROV=qwen; FLOOR=0;; esac' + NL +
       'if ! /research/d7/spc/yzyang4/venvs/critic/bin/python3 \\' + NL +
       '     /research/d7/spc/yzyang4/scripts/balance_guard.py "$PROV" "$FLOOR"; then' + NL +
       '  echo "$(date -u +%FT%TZ) HOLD $3: $PROV balance below floor"' + NL +
       '  exit 0' + NL +
       'fi' + NL +
       'TS="${4:-}"')
assert s.count(old) == 1, "anchor"
s = s.replace(old, new, 1)
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("pool_fill_once.sh: balance guard added (gen2*->qwen, else deepseek floor 25)")
