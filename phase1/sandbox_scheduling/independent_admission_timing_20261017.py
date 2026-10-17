"""Independent raw-event reconstruction of decision counts and remaining time.

No imports from lineage/proposal readers. Compare against their immutable export.
Does NOT independently reconstruct code lineage, scores, or unknown descendants.
"""
from datetime import datetime
import hashlib,json,re
from pathlib import Path

SPECS=(
 (18770,'scheduling-pooling-20261016-v3','adaptation-lineage-extension-20261017.safe.json','239068967985e3a3b6edacae54c0d6c41bb305a89679c986de2577eca933f322'),
 (18807,'scheduling-colocation-20261016-v1','adaptation-lineage-extension-20261017.safe.json','0be079dbf6a1e3d0d1773032b4725dc07cae59145e8b91b6f53d1c60ea934c83'),
 (18997,'scheduling-selective-20261017-v1','adaptation-lineage-20261017.safe.json','b207d27b0ae4f4083d5352c4ded9d6c867bde40267b06f826f8de4a11a686db0'),
 (18412,'scheduling-metric-deployment-20261015-v2','adaptation-lineage-20261017.safe.json','2f5cfaea084579f5d467f38a8ad5738e9ac9ad0f4780e9c6a31aef3b80a14803'))

def digest(b):return hashlib.sha256(b).hexdigest()
def read(p,pin,lines=False):
    b=p.read_bytes();assert digest(b)==pin
    assert not re.search(rb'(?i)(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,})',b)
    return [json.loads(x) for x in b.splitlines() if x.strip()] if lines else json.loads(b)

def main():
    results=[]
    for job,name,file,pin in SPECS:
        root=Path('/research/d7/spc/yzyang4')/name
        proposed=read(root/'proposal-opportunities-20261017.safe.json',pin)
        lineage=read(root/file,proposed['lineage_sha256']);plan=read(root/'plan.json',lineage['plan_sha256'])
        assert proposed['run_seconds']==plan['run_seconds']
        expect={(r['block'],r['request_key']):r for r in proposed['rows']};seen=set();counts={}
        for block in sorted({r['block'] for r in plan['schedule']}):
            er=f'generation-{block}/events.jsonl';events=read(root/er,lineage['source_hashes'][er],True)
            warm={e['run']:e['code_sha256'] for e in events if e['event']=='warm_start'}
            used={e['key'] for e in events if e['event']=='parent_used'}
            for e in events:
                if e['event']!='admitted' or e['role']!='improve':continue
                key=block,e['key'];assert key not in seen and key in expect;seen.add(key);r=expect[key]
                dr=f'episode-{e["run"]}/deadline.json';deadline=read(root/dr,lineage['source_hashes'][dr])
                start=datetime.fromisoformat(deadline['started_utc']).timestamp()
                remain=start+plan['run_seconds']-e['time'];assert abs(remain-r['remaining_seconds'])<1e-6
                assert r['index']==e['run'] and r['generated']==(e['key'] in used)
                new=e['parent']!=warm[e['run']];assert new==r['new_parent']
                band=next(label for threshold,label in ((300,'under300'),(600,'300to600'),(900,'600to900'),(float('inf'),'atleast900')) if remain<threshold)
                assert band==r['remaining_band'];k=('new' if new else 'warm')+'_'+band;counts[k]=counts.get(k,0)+1
        assert seen==set(expect)
        results.append(dict(job=job,admitted=len(seen),counts=counts,proposal_sha256=pin))
    out=dict(passed=True,reader_sha256=digest(Path(__file__).read_bytes()),cohorts=results,
        scope='Independent raw admission counts/timing only; scores and ancestry NOT independently re-extracted.',
        prior_attempt='Remote Node entry unavailable (command not found); no installation performed; local Node aggregation separately passed.')
    dest=Path(__file__).with_name('admission-timing-independent-20261017.safe.json')
    with dest.open('x') as f:json.dump(out,f,indent=2,sort_keys=True)
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
