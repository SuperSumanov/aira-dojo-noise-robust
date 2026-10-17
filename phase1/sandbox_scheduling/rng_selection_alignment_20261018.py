"""Read-only structure check; does NOT read scores, predictions, or labels.

Exact multiset matches are stronger than partial overlap; no exact match does
not establish that the underlying input sets are disjoint. Loader pairs are
not independent replicates. Full epoch hashes only compare completed epochs.
"""
import hashlib
import json
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/rng-selection-20261018-v2')
read=lambda p:json.loads(p.read_text())
p=read(R/'plan.json')
assert p['source_commit']=='7632bba196426ae1689e89a1d62671609d1d5296'
assert hashlib.sha256((R/'plan.json').read_bytes()).hexdigest()=='9e1bf0caa8964e6baaf9ccd8be247f9ddc802bfd6be137f88fc535a494082756'
out=[]
for b in range(6):
    for t in (0,1):
        rr=p['schedule'][4*b+2*t:4*b+2*t+2]
        paths=[R/f"episode-{r['index']}/training.safe.json" for r in rr]
        if not all(q.is_file() for q in paths):continue
        logs=[read(q).get('data_rng',[]) for q in paths]
        assert all(x['mode']==rr[0]['mode'] for ll in logs for x in ll)
        pairs=[]
        for a in logs[0]:
            for c in logs[1]:
                if a['input_multiset_sha256']!=c['input_multiset_sha256']:continue
                for i in range(min(len(a['epochs']),len(c['epochs']))):
                    x,y=a['epochs'][i],c['epochs'][i]
                    if not(x['completed'] and y['completed']):continue
                    assert x['n']==y['n']
                    pairs.append(dict(loaders=[a['loader'],c['loader']],epoch=i,n=x['n'],same_order=x['order_sha256']==y['order_sha256']))
        out.append(dict(task=t,mode=rr[0]['mode'],seed=rr[0]['seed'],
            loaders=[len(ll) for ll in logs],exact_input_multiset_matches=sum(a['input_multiset_sha256']==c['input_multiset_sha256'] for a in logs[0] for c in logs[1]),
            comparable_full_epochs=len(pairs),same_order_full_epochs=sum(x['same_order'] for x in pairs),
            addressed_alignment_holds=(all(x['same_order'] for x in pairs) if pairs and rr[0]['mode']=='addressed' else None)))
print(json.dumps(dict(read_scores=False,rows=out,
    boundary='Input and order identities only; no exact multiset match does not mean no shared samples. No quality, augmentation-equality, variance or independent-replicate claim.')))
