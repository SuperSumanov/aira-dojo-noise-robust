"""Independent arithmetic/paired identity verifier; no dependency on readout."""
import argparse,hashlib,json,math
from pathlib import Path

def verify(data):
    if data['role']!='live_conditioned_rescue_not_full_e2e':raise ValueError('estimand')
    allocation=data['allocation']
    if allocation['gpus']!=6 or not math.isclose(allocation['gpu_hours'],allocation['seconds']/600):raise ValueError('all resources')
    rows=data['rows'];expected={(1,False),(1,True),(2,False),(2,True)}
    if len(rows)!=4 or {(r['seed'],r['cache']) for r in rows}!=expected:raise ValueError('fixed pairs')
    deltas=[];unknown=0;valid=0
    for row in rows:
        if row['budget_seconds']!=2100:raise ValueError('same budget')
        if row['cache'] is not (row['lane']==row['seed']-1):raise ValueError('crossover')
        outcome=row['valid_accepted_submission']
        if outcome is None:unknown+=1
        elif type(outcome) is not bool:raise ValueError('outcome schema')
        if outcome:
            valid+=1
            if not (0<=row['accepted_seconds']<=2100):raise ValueError('late success')
            if not math.isfinite(row['independent_score']) or round(row['independent_score'],5)!=row['score']:raise ValueError('official numeric consistency')
        if outcome is not True and row['score'] is not None:raise ValueError('unaccepted score used')
    for seed in (1,2):
        treatment=next(r for r in rows if r['seed']==seed and r['cache']);baseline=next(r for r in rows if r['seed']==seed and not r['cache'])
        group,=[g for g in data['comparison']['groups'] if g['seed']==seed]
        if treatment['valid_accepted_submission'] is None or baseline['valid_accepted_submission'] is None:
            if group['status']!='UNKNOWN_NO_EFFECT_CLAIM':raise ValueError('unknown promoted')
            continue
        delta=int(treatment['valid_accepted_submission'])-int(baseline['valid_accepted_submission']);deltas.append(delta)
        if delta!=group['validity_delta']:raise ValueError('delta')
        if treatment['valid_accepted_submission'] and baseline['valid_accepted_submission']:
            for name,a,b in [('loss_delta_cache_minus_baseline',treatment['score'],baseline['score']),('first_accept_seconds_delta',treatment['accepted_seconds'],baseline['accepted_seconds'])]:
                if not math.isclose(group[name],a-b,abs_tol=1e-10):raise ValueError('paired arithmetic')
        elif group['loss_delta_cache_minus_baseline'] is not None or group['first_accept_seconds_delta'] is not None:raise ValueError('undefined conditional difference')
    mean=sum(deltas)/2 if len(deltas)==2 else None
    if data['comparison']['paired_validity_mean_delta']!=mean:raise ValueError('unknown denominator or paired mean')
    wins=deltas.count(1);losses=deltas.count(-1);ties=deltas.count(0);n=wins+losses
    p=min(1.0,2*sum(math.comb(n,k) for k in range(min(wins,losses)+1))/2**n) if n else 1.0
    return dict(status='PASS_INDEPENDENT_PAIRED_ARITHMETIC',physical_runs=2,episodes=4,valid_accepted=valid,unknown=unknown,
        validity_wins=wins,validity_losses=losses,validity_ties=ties,paired_sign_two_sided_p=p,
        no_population_confirmation=True,full_e2e_claim=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('summary',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    raw=args.summary.read_bytes();result=verify(json.loads(raw));result['summary_sha256']=hashlib.sha256(raw).hexdigest()
    with args.output.open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result,indent=2))
