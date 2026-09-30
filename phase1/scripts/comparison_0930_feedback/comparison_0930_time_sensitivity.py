"""Posthoc observation-window sensitivity; not an equal-budget causal comparison."""
import argparse,csv,hashlib,json,math,statistics
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
INPUT=ROOT.parent/'aira-dojo-codex-20260813/phase1/results/comparison_0930_readout_20261001'
EXPECTED={'rows.json':'f48c30558572dc6512a39301fe3914626c70a45c2dc9d97f1879d280fb2bf993',
          'numeric_trace.json':'b419063798df48d75875e28c4d8f32143a851ac362f0e6cdba1715f5825ed7c8'}
GRID=[3600,10800,21600,43200,64800,86400]
CONTRASTS=[('forets-selected','random'),('short','random'),('short','forets-selected')]

def trace(nodes):
    first=datetime.fromisoformat(nodes[0]['timestamp'].replace('Z','+00:00'))
    state={};out=[];previous=-1
    for n in nodes:
        elapsed=(datetime.fromisoformat(n['timestamp'].replace('Z','+00:00'))-first).total_seconds()
        assert elapsed>=previous;previous=elapsed
        if n['step']==0:state={}
        assert n['step'] not in state
        state[n['step']]=n
        selected=state[n['pointer']]
        out.append({'elapsed':elapsed,'score':selected['score'],'selected_step':selected['step']})
    return out

def endpoint(trajectory,horizon):
    assert trajectory[0]['elapsed']==0
    if horizon>trajectory[-1]['elapsed']:return {'observed':False,'score':None,'selected_step':None}
    row=next(r for r in reversed(trajectory) if r['elapsed']<=horizon)
    return {'observed':True,**row}

def stat(vals):
    return {'n':len(vals),'mean':statistics.mean(vals) if vals else None,'median':statistics.median(vals) if vals else None,
        'sd':statistics.stdev(vals) if len(vals)>1 else None}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,default=INPUT)
    ap.add_argument('--output',type=Path,default=ROOT/'comparison_0930_time_sensitivity_v3')
    args=ap.parse_args()
    loaded={}
    for name,pin in EXPECTED.items():
        raw=(args.input/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==pin;loaded[name]=json.loads(raw)
    rows=loaded['rows.json'];traces={r['run_digest']:trace(r['nodes']) for r in loaded['numeric_trace.json']}
    config={(r['task'],r['arm'],r['seed']):r for r in rows};paired=[];summaries=[]
    for task in sorted({r['task'] for r in rows}):
        for a,b in CONTRASTS:
            seeds=sorted({k[2] for k in config if k[:2]==(task,a)} & {k[2] for k in config if k[:2]==(task,b)})
            assert seeds,(task,a,b)
            for h in GRID+['pair_overlap']:
                group=[]
                for seed in seeds:
                    ar,br=config[(task,a,seed)],config[(task,b,seed)]
                    ta,tb=traces[ar['run_digest']],traces[br['run_digest']]
                    horizon=min(ta[-1]['elapsed'],tb[-1]['elapsed'],86400) if h=='pair_overlap' else h
                    ae,be=endpoint(ta,horizon),endpoint(tb,horizon)
                    both=ae['observed'] and be['observed'];av,bv=ae['score'],be['score']
                    delta=(av-bv)*(-1 if task=='petfinder-pawpularity-score' else 1) if both and av is not None and bv is not None else None
                    r={'task':task,'arm_a':a,'arm_b':b,'seed':seed,'horizon_kind':str(h),'seconds':horizon,
                      'run_a':ar['run_digest'],'run_b':br['run_digest'],'a_observed':ae['observed'],'b_observed':be['observed'],
                      'a_finite':both and av is not None,'b_finite':both and bv is not None,
                      'a_score':av if both else None,'b_score':bv if both else None,'directed_difference':delta,
                      'restart_present':ar['restart_segments']>1 or br['restart_segments']>1}
                    group.append(r);paired.append(r)
                finite=[r['directed_difference'] for r in group if r['directed_difference'] is not None]
                summaries.append({'task':task,'arm_a':a,'arm_b':b,'horizon_kind':str(h),'matched_seeds':len(group),
                    'both_observed':sum(r['a_observed'] and r['b_observed'] for r in group),
                    'a_only_finite':sum(r['a_finite'] and not r['b_finite'] for r in group),
                    'b_only_finite':sum(r['b_finite'] and not r['a_finite'] for r in group),
                    'difference':stat(finite),'a_wins':sum(d>0 for d in finite),'ties':sum(d==0 for d in finite),
                    'b_wins':sum(d<0 for d in finite)})
    out=args.output;out.mkdir()
    (out/'summary.json').write_text(json.dumps({'kind':'POSTHOC_LOGGED_TIME_SENSITIVITY_NOT_BUDGET_CERTIFICATE',
      'fixed_grid_seconds':GRID,'input_sha256':EXPECTED,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'groups':summaries,'limitations':['Censor after last recorded event; no evidence of completion.','Elapsed logging time is not necessarily active compute time.',
        'Same seed does not imply common randomness.','Different producer commits and hardware uncertainty remain.','No inference to same-budget causal benefit.']},indent=2,allow_nan=False))
    with (out/'paired.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
    print(json.dumps([r for r in summaries if r['horizon_kind'] in ('pair_overlap','43200')]))

if __name__=='__main__':main()
