"""Remote credential-first operator configuration metadata only."""
import hashlib,json,re,tarfile
from pathlib import Path,PurePosixPath
from discover_comparison_20260919 import SECRET

root=Path('/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6')
runs={'3277c81be72a1c30','58d3914785a2cfe1'}
rows=[]
with tarfile.open(root/'archives/spooky-author-identification.tar.gz','r|gz') as archive:
    for member in archive:
        p=PurePosixPath(member.name)
        if not member.isfile() or p.name!='dojo_config.json':continue
        run=hashlib.sha256(str(p.parent).encode()).hexdigest()[:16]
        if run not in runs:continue
        raw=archive.extractfile(member).read();hits=len(SECRET.findall(raw.decode()))
        obj=json.loads(SECRET.sub('[REDACTED]',raw.decode()));solver=obj['solver']
        debug=solver['operators']['debug']
        rows.append(dict(run=run,config_sha256=hashlib.sha256(raw).hexdigest(),credential_shapes=hits,
          operator_keys=sorted(debug),llm_keys=sorted(debug['llm']),
          generation={k:v for k,v in debug['llm'].get('generation_kwargs',{}).items()
                      if k in ('temperature','top_p','top_k','max_tokens','seed','extra_body','repetition_penalty','presence_penalty')},
          debug_memory=solver.get('debug_memory'),data_preview=solver.get('data_preview'),
          execution_timeout=solver.get('execution_timeout'),step_limit=solver.get('step_limit'),
          use_test_score=solver.get('use_test_score'),task_keys=sorted(obj['task'])))
if {r['run'] for r in rows}!=runs or len(rows)!=2:raise ValueError('scope')
text=json.dumps(rows,indent=2)
if SECRET.search(text):raise ValueError('unsafe output')
print(text)
