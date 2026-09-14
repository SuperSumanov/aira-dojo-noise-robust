"""Read only code-delivery hashes after closure; never print code or scores."""
import hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
sys.path.insert(0,str(ROOT/'source/src'))
from dojo.core.solvers.utils.response import extract_code
def h(s):return hashlib.sha256(s.encode()).hexdigest()
rows=[];total=0
for r in json.loads((ROOT/'prepared.json').read_bytes())['run_configs']:
    cfg=json.loads((ROOT/'configs'/(r['run_id']+'.json')).read_bytes())
    for p in sorted((Path(cfg['solver']['checkpoint_path'])/'forets-candidates-private').glob('batch-*.sqlite')):
        with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as db:raw,digest=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
        assert h(raw)==digest
        v=json.loads(raw)
        for c in v['task_calls']:
            if c['intent']['role']!='candidate':continue
            total+=1;code=v['candidates'][c['slot']]['node']['code'];actual=c['intent']['code_sha256']
            if h(code)!=actual:rows.append(dict(run_id=r['run_id'],pool=p.name,slot=c['slot'],raw_sha256=h(code),executed_sha256=actual,extract_sha256=h(extract_code(code)),matches_exact_native_extract=h(extract_code(code))==actual))
print(json.dumps(dict(total_candidate_calls=total,mismatches=rows,all_explained=all(r['matches_exact_native_extract'] for r in rows))))
