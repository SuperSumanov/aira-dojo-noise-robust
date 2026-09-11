"""Independent stdlib-only numerical readout; never import the producer."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

def verify(root):
    summary=json.loads((root/'summary.json').read_text())
    raw=(root/'predictions.private.csv').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==summary['predictions_sha256']
    by_task=defaultdict(lambda:defaultdict(list)); seen=set()
    with (root/'predictions.private.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            key=(row['run_sha'],int(row['step']))
            assert key not in seen;seen.add(key)
            y=int(row['target']);assert y in (0,1)
            v={m:float(row[m]) for m in ('prior','eventual','deadline')}
            assert all(math.isfinite(p) and 0<=p<=1 for p in v.values())
            by_task[row['task']][row['component']].append((y,v))
    assert len(seen)==summary['evaluated_rows'] and len(by_task)==6
    recomputed=[]
    for task, groups in sorted(by_task.items()):
        item={'task':task,'components':len(groups),'rows':sum(map(len,groups.values()))}
        for model in ('prior','eventual','deadline'):
            item[model+'_brier']=statistics.mean(statistics.mean((p[model]-y)**2 for y,p in group) for group in groups.values())
            item[model+'_logloss']=statistics.mean(statistics.mean(-(y*math.log(max(1e-15,p[model]))+(1-y)*math.log(max(1e-15,1-p[model])) ) for y,p in group) for group in groups.values())
        item['deadline_prevalence']=statistics.mean(statistics.mean(y for y,p in group) for group in groups.values())
        recomputed.append(item)
    for actual, expected in zip(recomputed,summary['per_task'],strict=True):
        assert actual.keys()==expected.keys()
        for k,v in actual.items():
            if isinstance(v,float):assert math.isclose(v,expected[k],rel_tol=1e-12,abs_tol=1e-12)
            else:assert v==expected[k]
    gate=True
    for baseline in ('prior','eventual'):
        deltas=[r[baseline+'_brier']-r['deadline_brier'] for r in recomputed]
        mean=statistics.mean(deltas);positive=sum(d>0 for d in deltas)
        assert math.isclose(mean,summary['comparisons'][baseline]['brier_improvement'],rel_tol=1e-12,abs_tol=1e-12)
        assert positive==summary['comparisons'][baseline]['positive_tasks']
        gate &= mean>=.01 and positive>=4
    assert gate==summary['investment_signal']
    return dict(status='PASS_NUMERICAL_AGGREGATION',rows=len(seen),tasks=len(by_task),
                components=sum(map(len,by_task.values())),investment_signal=gate,
                imports_producer=False,source_label_validation=False,bootstrap_recomputed=False,
                summary_sha256=hashlib.sha256((root/'summary.json').read_bytes()).hexdigest(),
                verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);args=p.parse_args()
    result=verify(args.root)
    with (args.root/'independent.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
