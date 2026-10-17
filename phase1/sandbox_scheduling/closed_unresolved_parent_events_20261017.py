"""Secondary event-only ancestry evidence for ALL eight unresolved returns.

Never overwrites journal-based receipts or fills a missing edge using score.
Only an exact unique child hash with a timed admission can support Improve.
"""
import json
from pathlib import Path
from closed_parent_delta_20261017 import SPECS
import closed_adaptation_lineage_20261017 as m


def main():
    rows=[];pins={}
    for job,name,file,pin in SPECS:
        root=Path('/research/d7/spc/yzyang4')/name
        assert m.sha(root/file)==pin
        origin=m.load(root/file);pins[str(job)]=pin
        def source(rel,lines=False):
            assert m.sha(root/rel)==origin['source_hashes'][rel]
            v=m.load(root/rel,lines)
            assert m.sha(root/rel)==origin['source_hashes'][rel]
            return v
        for c in (x for x in origin['candidates'] if not x['lineage_resolved']):
            i,n,b=c['index'],c['candidate'],c['block']
            receipt=source(f'episode-{i}/candidate-{n}.json')
            events=source(f'generation-{b}/events.jsonl',True)
            used=[e for e in events if e['event']=='parent_used' and e['run']==i and e['child']==receipt['code_sha256']]
            row={k:c[k] for k in ('index','candidate','block','task','valid','score','native_matches')}
            row.update(job=job,exact_generated_child_events=len(used),resolved_by_direct_event=False)
            if len(used)==1:
                e=used[0]
                a=[v for v in events if v['event']=='admitted' and v['key']==e['key']]
                assert len(a)==1 and a[0]['role']=='improve' and a[0]['parent']==e['parent']
                a=a[0]
                slot=source(f'block-{b}/budget-slot.json')['start']
                assert a['time']<=e['time']<=slot+c['pool_elapsed']
                warm=[v['code_sha256'] for v in events if v['event']=='warm_start' and v['run']==i]
                assert len(warm)==1
                parent=a['snapshot']['archive'][c['task']][e['parent']]['metric']
                sign=-1 if c['task']=='denoising-dirty-documents' else 1
                assert sign*parent==max(sign*v['metric'] for v in a['snapshot']['archive'][c['task']].values())
                gain=sign*(c['score']-parent) if c['valid'] else None
                row.update(resolved_by_direct_event=True,request_key=e['key'],new_parent=e['parent']!=warm[0],
                    parent_score=parent,gain_vs_parent=gain,parent_admitted_pool_elapsed=a['time']-slot)
            rows.append(row)
    assert len(rows)==8
    out=dict(reader_sha256=m.sha(__file__),helper_sha256=m.sha(m.__file__),lineage_pins=pins,rows=rows,
        limits=['Secondary direct-event evidence only; original journal-based unresolved status unchanged.',
                'No debug ancestry is inferred from temporal proximity, numeric score, or a missing journal.',
                'Exact child hash after Improve and earlier matching admission, not semantic proof of parent usage.',
                'No new scores, GPU calls, repaired experiment, or changed primary gate.'])
    dst=Path(__file__).with_name('unresolved-parent-events-20261017.safe.json')
    with dst.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(sha256=m.sha(dst),rows=rows),sort_keys=True))


if __name__=='__main__':main()
