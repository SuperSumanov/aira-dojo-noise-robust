"""Progress only: no candidate code, predictions or task outcome values."""
import json
import os
from collections import Counter
from pathlib import Path
from run_repair_transfer_20260913 import ROOT, budget_module, public_budget, now
from prepare_repair_transfer_20260913 import read


def main():
    report=dict(utc=now(),root=str(ROOT))
    for name in ('generation.pid',):
        p=ROOT/name
        if p.exists():
            value=p.read_text().strip()
            if not value.isdigit():raise ValueError('pid schema')
            try:os.kill(int(value),0);alive=True
            except ProcessLookupError:alive=False
            report[name]=dict(pid=int(value),alive=alive)
    gen=[read(p) for p in sorted(ROOT.glob('generated-*.json'))]
    report['generation']=dict(recorded=len(gen),states=dict(Counter(r['status'] for r in gen)))
    if (ROOT/'generation-finished.json').exists():
        f=read(ROOT/'generation-finished.json')
        report['generation_finished']={k:f[k] for k in ('utc','planned','completed','generated','complete','seconds')}
    report['billing']=public_budget(budget_module().snapshot(ROOT/'paid.sqlite'))
    blocks=[]
    for b in (0,1):
        work=ROOT/f'block-{b}';row=dict(block=b,prepared=(work/'prepared.json').exists())
        if (work/'launch.json').exists():row['job']=read(work/'launch.json')['job']
        row['executed_records']=len(list(work.glob('result-*.json'))) if work.exists() else 0
        row['finished']=(work/'execution-finished.json').exists()
        if row['finished']:
            f=read(work/'execution-finished.json')
            row.update({k:f[k] for k in ('planned','completed','complete','stop_reason')})
        blocks.append(row)
    report['blocks']=blocks
    print(json.dumps(report))


if __name__=='__main__':main()
