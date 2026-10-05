"""Closed-only failure categories, never raw programs, labels or model replies."""
import collections,json,re,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/implementation-reset-20261005-v1')
assert (R/'closed.json').exists(), 'not closed'
sys.path.insert(0,str(R))
from implementation_reset_20261005 import read,write
rows=[]
for i in range(4):
    ep=R/f'episode-{i}';types=collections.Counter();keywords=set();calls=[]
    for gp in sorted(ep.glob('action-*/generation.private.json')):
        d=read(gp);text='\n'.join(str(m.get('content','')) for m in d.get('info',{}).get('prompt_messages',[]))
        text=re.sub(r'\x1b\[[0-9;]*m','',text)
        types.update(re.findall(r'(?m)^\s*([A-Za-z]+(?:Error|Exception))\s*:',text))
        keywords.update(re.findall(r"unexpected keyword argument ['\"]([A-Za-z_][A-Za-z_0-9]*)['\"]",text))
        usage=d.get('info',{}).get('usage',{})
        calls.append({k:usage.get(k) for k in ('prompt_tokens','completion_tokens','latency','success')})
    execution=[]
    for rp in sorted(ep.glob('action-*/result.json')):
        r=read(rp);execution.append({k:r.get(k) for k in ('valid','exit_code','timed_out','exec_seconds','kind')})
    rows.append(dict(index=i,generation_calls_returned=len(calls),calls=calls,observed_prior_exception_types=dict(types),unexpected_keywords=sorted(keywords),execution=execution))
report={'scope':'closed first-source qualification only; diagnostic not new effect','rows':rows}
write(R/'readout-v1'/'failure-categories.json',report)
print(json.dumps(report))
