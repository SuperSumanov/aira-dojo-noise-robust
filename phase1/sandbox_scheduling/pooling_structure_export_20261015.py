"""Export ONLY completed-pool timing, anonymized session slots and deadlines.

No candidate body, outcome, prediction, label, model response or grade is read.
Cancelled-before-admission requests stay explicit and have unknown duration.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from compute_split_screen_20261015 import PINNED, sha, read
from effort_pressure_diagnostic_20261012 import structural_events, state_changes


def session(key):
    m = re.fullmatch(r'(\d+):(\d+)', key)
    if not m:
        raise ValueError('unknown execution key schema')
    return int(m.group(1))


def main(root, screen, dest):
    root=Path(root); baseline=read(screen); pin,n,nb=PINNED[root.name]
    assert sha(root/'plan.json')==pin==baseline['plan_sha256']
    plan=read(root/'plan.json');closed=read(root/'closed.json')
    assert closed['complete']==n and closed['error'] is None
    results=[];sources={}
    for b in range(nb):
        specs=[s for s in plan['schedule'] if s['block']==b]
        assert len(specs)==8
        tasks=sorted({s['task'] for s in specs});assert len(tasks)==2
        spec={s['index']:s for s in specs}
        budget=read(root/f'block-{b}/budget-slot.json');zero=budget['start']
        deadlines={}
        for s in specs:
            f=root/f"episode-{s['index']}/deadline.json";d=read(f)
            sources[str(f.relative_to(root))]=sha(f)
            assert d['budget_seconds']==plan['run_seconds']==1800 and d['cleanup_is_score_time'] is False
            deadlines[s['index']]=datetime.fromisoformat(d['started_utc']).timestamp()+1800-zero
        jobs=[];cancelled=[]
        for lane in range(4):
            f=root/f'queue-{b}-{lane}/events.jsonl';relative=str(f.relative_to(root))
            assert sha(f)==baseline['source_hashes'][relative]
            sources[relative]=sha(f);events=structural_events(f,False)
            state_changes(events,1)
            pending={};active={}
            for e in events:
                k=e['key'];sid=session(k);s=spec[sid]
                assert s['lane']==lane
                if e['kind']=='queued':pending[k]=e['time']-zero
                elif e['kind']=='admitted':active[k]=e['time']-zero
                elif e['kind']=='released':
                    jobs.append(dict(session=s['slot'],task=tasks.index(s['task']),lane=lane,
                        arrival=pending.pop(k),original_start=active[k],duration=e['time']-zero-active.pop(k),
                        deadline=deadlines[sid]))
                elif e['kind']=='cancelled':
                    cancelled.append(dict(session=s['slot'],task=tasks.index(s['task']),lane=lane,
                        arrival=pending.pop(k),cancelled_at=e['time']-zero,deadline=deadlines[sid],duration=None))
            assert not pending and not active
        reference=baseline['safe_structural_streams'][b]['execution_jobs']
        norm=lambda rows:sorted((round(j['arrival'],5),round(j['original_start'],5),round(j['duration'],5)) for j in rows)
        transformed=[dict(arrival=j['arrival']-zero,original_start=j['original_start']-zero,duration=j['duration']) for j in reference]
        assert norm(transformed)==norm(jobs)
        results.append(dict(block=b,arm=specs[0]['arm'],jobs=jobs,cancelled=cancelled,
            assigned_sessions=8,pool_seconds=budget['actual_seconds'],
            original_completed_by_search_deadline=sum(j['original_start']+j['duration']<=j['deadline'] for j in jobs),
            source_queue_hashes_match_first_screen=True))
    result=dict(kind='closed_pool_timing_export',plan_sha256=pin,screen_sha256=sha(screen),
        script_sha256=sha(__file__),assigned=n,pools=results,source_hashes=sources,
        quality_claim=False,new_gpu_jobs=0,
        limits=['Post-hoc observed execution requests only; cancelled requests have unknown durations and remain listed.',
                'Release includes cleanup; completion by search deadline is a conservative resource-release count, NOT valid feedback or final-score count.',
                'Fixed arrival replay ignores feedback-dependent future work and changed CPU contention. Session slots are structural, not model or candidate identities.'])
    with Path(dest).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(assigned=n,pools=len(results),jobs=sum(len(p['jobs']) for p in results),
        cancelled_unknown_duration=sum(len(p['cancelled']) for p in results),output_sha256=sha(dest))))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('screen');ap.add_argument('out')
    a=ap.parse_args();main(a.root,a.screen,a.out)
