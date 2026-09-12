"""Secondary sensitivity: enumerate every score-tied top2 set and shared unknown.

Never alters the frozen selector or original readout. Bounds are NOT confidence intervals.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

def one(rows,scores):
    if len(rows)!=4 or len(scores)!=4:raise ValueError('four candidates')
    sets=list(itertools.combinations(range(4),2))
    optimum=max(sum(scores[i] for i in st) for st in sets)
    admissible=[st for st in sets if sum(scores[i] for i in st)==optimum]
    unknown=[i for i,r in enumerate(rows) if r['valid'] is None]
    means=[];allvalues=[]
    for bits in itertools.product((0,1),repeat=len(unknown)):
        valid=[int(r['valid']) if r['valid'] is not None else None for r in rows]
        for i,b in zip(unknown,bits):valid[i]=b
        gains=[sum(valid[i] for i in st)/2-sum(valid)/4 for st in admissible]
        means.append(sum(gains)/len(gains));allvalues.extend(gains)
    return dict(admissible_top2_sets=admissible,
        uniformly_randomized_cutoff_tie_gain_bounds=[min(means),max(means)],
        arbitrary_admissible_tie_gain_bounds=[min(allvalues),max(allvalues)])

def analyze(summary,prepared):
    if len(summary['pools'])!=4 or len(prepared['pools'])!=4:raise ValueError('whole four-pool scope')
    rows=[]
    for pool,p in zip(summary['pools'],prepared['pools']):
        if pool['parent_run_id']!=p['parent_run_id']:raise ValueError('pool alignment')
        if [r['code_sha256'] for r in pool['rows']]!=p['code_sha256']:raise ValueError('code alignment')
        rows.append(dict(task=pool['task'],seed=pool['seed'],frozen_gain_bounds=pool['validity_gain_bounds'],**one(pool['rows'],p['borda'])))
    aggregate={}
    for key in ('frozen_gain_bounds','uniformly_randomized_cutoff_tie_gain_bounds','arbitrary_admissible_tie_gain_bounds'):
        aggregate[key]=[sum(r[key][i] for r in rows)/4 for i in (0,1)]
    return dict(role='secondary_posthoc_cutoff_tie_sensitivity',rows=rows,four_pool_equal_weight_bounds=aggregate,
        limitation='Finite-pool accounting, not sampling confidence intervals. The original slot-ascending selector remains unchanged. A favorable frozen tie must not be generalized as reliable ranking ability.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    sb=(a.directory/'pool-completion-summary.json').read_bytes();pb=(a.directory/'prepared.json').read_bytes()
    if hashlib.sha256(sb).hexdigest()!='4af0927191826f5c574f5c6caafe61337651c4d4aca62a96badcd6252749afb6' or hashlib.sha256(pb).hexdigest()!='959590741963d55dc60d53d45b604bd5e0344fb31b221e0a2d2deb34812d4d16':raise ValueError('input digest')
    value=analyze(json.loads(sb),json.loads(pb));value['reader_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(json.dumps(value,indent=2,allow_nan=False))
