"""Read-only actual gateway port audit of closed positive batches.

Returns ports/times/hash only; no raw log line, environment or credential export.
Fallback to another port is allowed only because the frozen server reads its
own process's announced address. Missing/multiple starts remain unverified.
"""
import json
from pathlib import Path
import re
from lifecycle_pilot import read,sha

B=Path('/research/d7/spc/yzyang4')

def main():
    batches=[]
    for name in ('scheduling-neural-qualified-overlap-20261008-evening-v1',
                 'scheduling-neural-full-confirmation-20261008-v1'):
        root=B/name;rows=[]
        for i in range(12):
            ep=root/f'episode-{i}';log=ep/'worker.private.log'
            raw=log.read_text(errors='replace')
            ports=[int(p) for p in re.findall(r'is available at http://[^:\s]+:(\d+)',raw)]
            done=read(ep/'completed.json')
            rows.append(dict(index=i,start=done['start'],end=done['end'],ports=ports,
                             log_sha256=sha(log)))
        overlapping=[]
        for a in rows:
            for b in rows:
                if a['index']>=b['index'] or min(a['end'],b['end'])<=max(a['start'],b['start']):continue
                verified=len(a['ports'])==len(b['ports'])==1 and a['ports'][0]!=b['ports'][0]
                overlapping.append(dict(indices=[a['index'],b['index']],disjoint_announced_ports=verified))
        batches.append(dict(root=name,rows=rows,overlapping=overlapping,
                            all_overlap_ports_distinct=bool(overlapping) and all(x['disjoint_announced_ports'] for x in overlapping),
                            limitation='Source shows old override used an unused function name. Actual ready ports, not requested ports, determine connection endpoints. This audit does not establish the cause of past readiness failures.'))
    print(json.dumps(batches,sort_keys=True))

if __name__=='__main__':main()
