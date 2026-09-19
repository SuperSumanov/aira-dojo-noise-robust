"""Independent closed-pool pair enumeration, without producer scoring helpers."""
import argparse,hashlib,json,math
from pathlib import Path

def verify(data):
    rows=data['rows'];assert len(rows)==18 and sorted(r['index'] for r in rows)==list(range(18))
    proofs=[]
    for seed in (1,2,3):
        rr=[r for r in rows if r['seed']==seed];assert len(rr)==6 and len({r['slot'] for r in rr})==6
        assert sum(r['original_selected'] for r in rr)==2
        expected=next(x for x in data['pools'] if x['seed']==seed)
        if any(r['valid'] is None for r in rr):
            assert expected['status']=='UNKNOWN_NO_EFFECT_CLAIM';proofs.append(dict(seed=seed,status='unknown'));continue
        original=[r for r in rr if r['original_selected'] and r['valid']]
        chosen=min((r['score'] for r in original),default=None);win=loss=tie=any_valid=valid_total=0;gains=[]
        for i in range(6):
            for j in range(i+1,6):
                valid=[r for r in (rr[i],rr[j]) if r['valid']]
                valid_total+=len(valid);any_valid+=bool(valid)
                other=min((r['score'] for r in valid),default=None)
                if chosen is not None and other is not None:
                    gains.append(other-chosen);win+=chosen<other;loss+=chosen>other;tie+=chosen==other
                elif chosen is None and other is None:tie+=1
                elif chosen is None:loss+=1
                else:win+=1
        assert (win,tie,loss)==tuple(expected['selected_vs_all_uniform_pairs'][k] for k in ('wins','ties','losses'))
        assert win+tie+loss==15 and expected['selected_valid']==len(original)
        assert math.isclose(expected['uniform_probability_any_valid'],any_valid/15)
        assert math.isclose(expected['uniform_expected_valid'],valid_total/15)
        if gains:assert math.isclose(expected['conditional_both_pairs_valid_mean_oriented_gain'],sum(gains)/len(gains),abs_tol=1e-12)
        proofs.append(dict(seed=seed,status='verified',wins=win,ties=tie,losses=loss))
    return dict(status='INDEPENDENT_PAIR_ENUMERATION_PASS',pools=proofs)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('summary',type=Path);args=a.parse_args()
    raw=args.summary.read_bytes();out=verify(json.loads(raw));out['summary_sha256']=hashlib.sha256(raw).hexdigest()
    with args.summary.with_name('independent-pairs.json').open('x') as h:json.dump(out,h,indent=2)
    print(json.dumps(out,indent=2))
