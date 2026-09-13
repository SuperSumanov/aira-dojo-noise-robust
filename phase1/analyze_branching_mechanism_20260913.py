"""Post-closure mechanism checks; no fabricated outcomes for unexecuted code."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
from forets_environment_build_20260912 import read,write,encode,sha
from audit_forets_chain_geometry_20260913 import geometry

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')


def inspect_calls(snapshots, journal_ids):
    counts=Counter();partial=[]
    for value in snapshots:
        for call in value['task_calls']:
            role=call['intent']['role'];counts[role+'_attempts']+=1
            if call['state']=='returned':
                meta=call['execution_metadata']
                outcome='timeout' if meta['timed_out_reported'] else 'exit_zero' if meta['exit_code_reported']==0 else 'exit_nonzero'
                counts[role+'_'+outcome]+=1
            else:counts[role+'_'+call['state']]+=1
        if value['phase']!='complete':
            original=[c for c in value['task_calls'] if c['intent']['role']=='candidate']
            partial.append(dict(step=value['binding']['step'],phase=value['phase'],
                attempted_candidates=len(original),returned_candidates=sum(c['state']=='returned' for c in original),
                parsed_candidates_in_final_journal=sum(
                    c['state']=='returned' and value['candidates'][c['slot']]['node']['id'] in journal_ids for c in original)))
    return dict(execution_counts=dict(counts),partial_batches=partial)


def run():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('whole matrix closure required')
    summary=read(ROOT/'common-start-summary.json',finish['files']['common-start-summary.json'])
    rows=[]
    for r in summary['rows']:
        rid=r['run_id'];directory=ROOT/'runs'/rid/'checkpoint';journal=directory/'journal.jsonl'
        nodes=[json.loads(l) for l in journal.read_bytes().splitlines() if l.strip()] if journal.exists() else None
        snapshots=[]
        for p in sorted((directory/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(p.read_bytes())
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:
                raw,digest=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(raw.encode())!=digest or sha(p.read_bytes())!=before:raise ValueError('snapshot drift')
            snapshots.append(json.loads(raw))
        counts=inspect_calls(snapshots,set(n['id'] for n in nodes) if nodes else set())
        logs=list((ROOT/'runs/srun_pool').glob('*/identities/'+rid+'*.bounded/execution/stderr.private.log'))
        if len(logs)>1:raise ValueError('duplicate attempts')
        wire=Counter();readiness=Counter();waits=[];rejections=0
        if logs:
            for line in logs[0].read_text(errors='replace').splitlines():
                if '] KERNEL_WIRE {' in line:
                    event=json.loads(line.split('] KERNEL_WIRE ',1)[1]);wire[event['event']]+=1
                if '] kernel_handshake {' in line:
                    event=json.loads(line.split('kernel_handshake ',1)[1]);readiness[str(event['success'])]+=1
                match=re.search(r'\] reservation_backpressure seconds=([0-9.]+) polls=([0-9]+)$',line)
                if match:waits.append(float(match[1]))
                if '] reservation_rejected total_nusd=' in line:rejections+=1
        rows.append(dict(run_id=rid,task=r['task'],seed=r['seed'],arm=r['arm'],
            journal_present=nodes is not None,geometry=geometry(nodes) if nodes is not None else None,
            **counts,wire_events=dict(wire),handshakes=dict(readiness),reservation_wait_events=len(waits),
            maximum_single_reservation_wait_seconds=max(waits,default=0),reservation_rejections=rejections))
    report=dict(source_tree=summary['source_tree'],summary_sha256=finish['files']['common-start-summary.json'],rows=rows,
        limitation='Exit zero is not external submission validity. Parsed nodes in partial batches are not retrospectively eligible incumbents. Concurrent reservation waits are not additive wall time. No unexecuted outcomes or causal mechanism mediation inferred.')
    digest=write(ROOT/'branching-mechanism.json',encode(report));print(json.dumps(dict(rows=rows,sha256=digest)))


if __name__=='__main__':run()
