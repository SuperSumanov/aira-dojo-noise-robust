"""Label-free post-closure prediction geometry. Never an efficacy estimate."""
import argparse,csv,hashlib,json,math
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
ALLOWED={'state-feedback-pizza-20261002-v1':'4b95fcc575c2f8fa438bd3737d05ec6f40ffa0aa2bfdfc89de38e76e71979b5b',
         'public-example-feedback-20261003-v1':'40e6bc3301c1db52fa09a794577c0b5dc95533302b0e460a044942a6485c5376'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def pred(p):
    with p.open(newline='') as f:rr=list(csv.DictReader(f))
    out={r['request_id']:float(r['requester_received_pizza']) for r in rr}
    assert len(out)==len(rr) and all(math.isfinite(v) for v in out.values())
    return out
def compare(a,b):
    assert set(a)==set(b)
    keys=sorted(a);orders=lambda x,y:(x>y)-(x<y)
    changed=0;ties_changed=0;total=0
    for i,k in enumerate(keys):
        for q in keys[:i]:
            x,y=orders(a[k],a[q]),orders(b[k],b[q]);total+=1
            changed+=x!=y;ties_changed+=(x==0)!=(y==0)
    # Independent rank-partition check of exact weak ordering, including ties.
    def partition(p):
        ranks={v:i for i,v in enumerate(sorted(set(p.values())))}
        return tuple(ranks[p[k]] for k in keys)
    assert (changed==0)==(partition(a)==partition(b))
    return dict(n=len(keys),pair_comparisons=total,changed_orders=changed,ties_changed=ties_changed,
                identical_numeric_predictions=all(a[k]==b[k] for k in keys),
                rank_equivalent=changed==0,max_absolute_change=max(abs(a[k]-b[k]) for k in keys))
def main():
    a=argparse.ArgumentParser();a.add_argument('root',choices=list(ALLOWED));x=a.parse_args();r=BASE/x.root
    assert sha(r/'plan.json')==ALLOWED[x.root] and read(r/'closed.json')['service_closed']
    plan=read(r/'plan.json');out=[];inputs={}
    for s in plan['schedule']:
        if s['task']!='random-acts-of-pizza':continue
        ep=r/f'episode-{s["index"]}';start=ep/'action-0/submission.private.csv'
        if not start.exists():continue
        initial=pred(start);inputs[str(start.relative_to(r))]=sha(start)
        for action in sorted(ep.glob('action-*')):
            step=int(action.name.split('-')[-1]);result=action/'result.json'
            if step==0 or not result.exists() or not read(result)['valid']:continue
            path=action/'submission.private.csv';values=pred(path)
            inputs[str(path.relative_to(r))]=sha(path)
            out.append(dict(index=s['index'],arm=s['arm'],seed=s['seed'],step=step,**compare(initial,values)))
    print(json.dumps(dict(root=x.root,plan_sha256=ALLOWED[x.root],valid_new_candidates=len(out),
        exact_prediction_copies=sum(z['identical_numeric_predictions'] for z in out),
        nonidentical_rank_equivalent=sum(z['rank_equivalent'] and not z['identical_numeric_predictions'] for z in out),
        changed_order=sum(not z['rank_equivalent'] for z in out),rows=out,input_hashes=inputs,
        limitation='Only observed finite prediction vectors, not global program equivalence. No labels read. Retrospective diagnostic, not novel algorithm or cross-task efficacy.'),sort_keys=True))
if __name__=='__main__':main()
