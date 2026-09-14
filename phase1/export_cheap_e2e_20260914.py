"""Closed verified result export and explicitly secondary baseline contrast."""
import io,json,tarfile
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import BASE,read,checked,sha
ROOT=BASE/'forets-wallclock-20260912-km65uuej'
def main():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified' or finish['summary_sha256']!='a2024478c6aa23feb7457d8d45738b51c622725b71eeba928af5e4d0a9dcac82':raise ValueError('complete frozen results')
    names=dict(finish['files']);names.update({'cheap-selector-independent.json':'1bc25e391e6c2022cd174a5d16e3a682c6eef55bb4325ff8b841e0dd43750e6f','cheap-reservation-waits.json':'8cfd4731ffed6469806854228a95e91b679e36ff7b9d1e37952cd4a3bdc467d0'})
    data={n:checked(ROOT/n,h) for n,h in names.items()};s=json.loads(data['cheap-selector-summary.json']);rows=s['rows'];contrast=[]
    for task in ('leaf-classification','spaceship-titanic'):
        for seed in (46,47):
            u=next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,'uniform'))
            short=next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,'short_code'))
            technical=u['technical_eligible'] and short['technical_eligible'];gain=None;sign=None
            if technical:
                if u['action_valid'] and short['action_valid']:
                    gain=(short['action_score']-u['action_score'])*(-1 if task=='leaf-classification' else 1);sign=(gain>0)-(gain<0)
                else:sign=int(short['action_valid'])-int(u['action_valid'])
            contrast.append(dict(task=task,seed=seed,uniform_score=u['action_score'],short_code_score=short['action_score'],gain=gain,sign=sign,technical_comparable=technical))
    posthoc=dict(role='secondary_posthoc_short_code_vs_uniform_not_original_critic_primary',source_summary_sha256=finish['summary_sha256'],pairs=contrast,
        wins=sum(p['sign']==1 for p in contrast),ties=sum(p['sign']==0 for p in contrast),losses=sum(p['sign']==-1 for p in contrast),unknown=sum(p['sign'] is None for p in contrast),
        limitations='Comparison among original controls noticed at full readout. Small paired development sample and shared reservation contention; not causal confirmation or replacement of failed original investment gate.')
    data['short-code-secondary.json']=(json.dumps(posthoc,sort_keys=True)+'\n').encode()
    data['readout-finished.json']=checked(ROOT/'readout-finished.json')
    data['manifest.json']=(json.dumps({n:dict(sha256=sha(raw),bytes=len(raw)) for n,raw in data.items()},sort_keys=True)+'\n').encode()
    dest=Path(__file__).with_name('cheap-e2e-public-20260914.tar')
    with dest.open('xb') as f,tarfile.open(fileobj=f,mode='w') as archive:
        for name,raw in sorted(data.items()):
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600;info.mtime=0;archive.addfile(info,io.BytesIO(raw))
    print(json.dumps(dict(path=str(dest),sha256=sha(dest.read_bytes()),secondary=posthoc,
        rows=[{k:r[k] for k in ('run_id','task','seed','arm','action_score','technical_eligible','pools','selected_pools','candidate_executions','api_cost_usd')} for r in rows])))
if __name__=='__main__':main()
