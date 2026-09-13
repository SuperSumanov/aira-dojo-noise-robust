"""Bounded, credential-screened error messages from closed T1 only."""
import json
from pathlib import Path
import re
from diagnose_repair_transfer_20260913 import ROOT, safe


def main():
    closed=json.loads(safe(ROOT/'readout-finished.json'))
    summary=json.loads(safe(ROOT/'summary.json',closed['summary_sha256']))
    rows=[]
    for block in (0,1):
        work=ROOT/f'block-{block}'
        for item in json.loads(safe(work/'prepared.json'))['rows']:
            p=work/f'result-{item["local_index"]}.json'
            if not p.exists():
                continue
            result=json.loads(safe(p,summary['proof'][str(p)]))
            messages=[]
            if result.get('output_sha256'):
                text=safe(work/f'program-{item["local_index"]}.txt',result['output_sha256'])
                text=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',text)
                messages=[line[:400] for line in text.splitlines() if re.match(r'^[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception):',line)]
            rows.append(dict(index=item['index'],case=item['case'],task=item['task'],arm=item['arm'],
                status=result['status'],error_type=result.get('error_type'),cleanup_error=result.get('cleanup_error'),
                wall_seconds=result['wall_seconds'],execution_seconds=result.get('execution_seconds'),
                bounded_last_exception_messages=messages[-2:]))
    print(json.dumps(rows))


if __name__=='__main__':
    main()
