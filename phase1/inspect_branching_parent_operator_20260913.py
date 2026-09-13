"""Classify all closed parent choices, without exporting candidate programs."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')
def sha(b):return hashlib.sha256(b).hexdigest()
def run():
    finish=json.loads((ROOT/'readout-finished.json').read_bytes())
    raw=(ROOT/'common-start-summary.json').read_bytes()
    if finish['status']!='verified' or sha(raw)!=finish['files']['common-start-summary.json']:raise ValueError('closure')
    summary=json.loads(raw);rows=[]
    for r in summary['rows']:
        cp=ROOT/'runs'/r['run_id']/'checkpoint'
        journal=cp/'journal.jsonl'
        nodes={n['id']:n for n in (json.loads(x) for x in journal.read_bytes().splitlines())} if journal.exists() else {}
        for path in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            h=sha(path.read_bytes())
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                value,digest=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(value.encode())!=digest or h!=sha(path.read_bytes()):raise ValueError('snapshot drift')
            d=json.loads(value);parent=nodes.get(d['binding']['parent_id'])
            rows.append(dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],
                step=d['binding']['step'],phase=d['phase'],parent_found=parent is not None,
                parent_is_synthetic_root=(parent['step']==0 and not parent['code'] and not parent['parents']) if parent else None,
                parent_executed_seconds=parent.get('exec_time') if parent else None,
                operators=[c['node']['operators_used'] if c['node'] is not None else None for c in d['candidates']],snapshot_sha256=h))
    result=dict(role='all_closed_parent_choices_not_effect',rows=rows,summary_sha256=sha(raw),
        inspector_sha256=sha(Path(__file__).read_bytes()))
    with (ROOT/'branching-parent-operators.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
if __name__=='__main__':run()
