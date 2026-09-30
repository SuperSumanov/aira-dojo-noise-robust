"""Independent prefix slicing and native-ranking check, no import of producer."""
import argparse,csv,json,math,hashlib
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT.parent/'aira-dojo-codex-20260813/phase1/results/comparison_0930_readout_20261001'
ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,default=DATA);ap.add_argument('--output',type=Path,default=ROOT/'comparison_0930_time_sensitivity_v3')
args=ap.parse_args();DATA=args.input;OUT=args.output
rows=json.loads((DATA/'rows.json').read_text())
traces={r['run_digest']:r['nodes'] for r in json.loads((DATA/'numeric_trace.json').read_text())}
config={r['run_digest']:r for r in rows}

def at(nodes,t):
    times=[datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')).timestamp() for r in nodes]
    # Microsecond rounding may differ from datetime.timedelta by <1 microsecond.
    elapsed=[round(x-times[0],6) for x in times]
    if elapsed[-1]<t-1e-6:return False,None
    prefix=[n for e,n in zip(elapsed,nodes) if e<=t+1e-6]
    root=max(i for i,n in enumerate(prefix) if n['step']==0)
    active=prefix[root:]
    pool=[n for n in active if not n['buggy'] and type(n['maximize']) is bool]
    pool.sort(key=lambda n:(n['metric'] is not None,(n['metric'] if n['maximize'] else -n['metric']) if n['metric'] is not None else 0),reverse=True)
    winner=pool[0] if pool else active[0]
    assert winner['step']==active[-1]['pointer']
    return True,winner['score']

compared=0
with (OUT/'paired.csv').open(newline='') as f:
    rr=list(csv.DictReader(f))
for r in rr:
    ar,br=config[r['run_a']],config[r['run_b']]
    assert ar['task']==br['task']==r['task'] and ar['seed']==br['seed']==int(r['seed'])
    assert ar['arm']==r['arm_a'] and br['arm']==r['arm_b']
    t=float(r['seconds']);ae,av=at(traces[r['run_a']],t);be,bv=at(traces[r['run_b']],t)
    assert ae==(r['a_observed']=='True') and be==(r['b_observed']=='True')
    for field,value in [('a_score',av if ae and be else None),('b_score',bv if ae and be else None)]:
        assert (r[field]=='')==(value is None)
        if value is not None:assert math.isclose(float(r[field]),value,rel_tol=1e-12,abs_tol=1e-12)
    delta=(av-bv)*(-1 if r['task']=='petfinder-pawpularity-score' else 1) if ae and be and av is not None and bv is not None else None
    assert (r['directed_difference']=='')==(delta is None)
    if delta is not None:assert math.isclose(float(r['directed_difference']),delta,rel_tol=1e-12,abs_tol=1e-12)
    compared+=1
receipt={'status':'PASS','paired_horizons':compared,'prefix_selections':2*compared,
 'method':'Independently slice each full event prefix, reset at latest root, sort native metrics, then compare external score.',
 'paired_sha256':hashlib.sha256((OUT/'paired.csv').read_bytes()).hexdigest(),
 'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (OUT/'independent.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt))
