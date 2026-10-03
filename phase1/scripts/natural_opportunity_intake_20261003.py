import ast,hashlib,json,os,re,sys
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');R=B/'natural-opportunity-20261003-v1'
DONORS=[('root-failure-randomized-gpu27-20260927-v1',0),('root-failure-randomized-gpu27-20260927-v1',1),('root-failure-text-tasks-gpu27-20260928-v2',1),('root-failure-randomized-gpu27-20260927-v1',3),('root-failure-randomized-gpu27-20260927-v1',2),('root-failure-text-unstarted-gpu27-20260928-v1',0)]
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def h(b):return hashlib.sha256(b).hexdigest()
def save(p,x):
    with p.open('x') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False)
os.umask(0o077)
if sys.argv[1]=='freeze':
    R.mkdir();(R/'starts').mkdir();records=[]
    for i,(name,run) in enumerate(DONORS):
        donor=B/name;jp=donor/f'run-{run}/checkpoint/journal.jsonl';cp=donor/f'configs/run-{run}.json'
        raw=jp.read_bytes();cr=cp.read_bytes()
        if SECRET.search(raw) or SECRET.search(cr):raise ValueError('credential shape')
        rows=[json.loads(x) for x in raw.splitlines() if x.strip()];cfg=json.loads(cr)
        eligible=[(j,x) for j,x in enumerate(rows) if x.get('code') and x.get('is_buggy') is False and x.get('metric_info',{}).get('execution_started') is True and x.get('metric_info',{}).get('submission_sha256')]
        rec=dict(index=i,donor=name,run=run,task=cfg['task']['name'],journal_sha256=h(raw),config_sha256=h(cr),seed=cfg['metadata']['seed'],available=bool(eligible),num_rows=len(rows))
        if eligible:
            j,x=eligible[0];code=x['code'];ast.parse(code)
            rec.update(row=j,code_sha256=h(code.encode()),historical_submission_sha256=x['metric_info']['submission_sha256'])
            (R/'starts'/f'{i}.py').write_text(code)
            save(R/'starts'/f'{i}.config.private.json',cfg)
        records.append(rec)
    save(R/'intake.json',dict(selection='first historically executed valid submission within each of six prelisted development runs; no score ranking; unavailable retained',
        source_commit='a284f3df7e8239a042765a329c81282643a4d5a1',states=records,
        limitations='Retrospective development run roster previously used in October1 pilot. New first-valid rows differ from first-executed selection. Cold rebuild from natural program, NOT exact native workspace/history continuation. No new cohort/generalization claim.',
        max_modifications_per_state=2,paid_api=0,protected_opened=False))
    print(json.dumps(dict(intake_sha256=h((R/'intake.json').read_bytes()),states=records)))
elif sys.argv[1]=='code':
    idx=int(sys.argv[2]);code=(R/'starts'/f'{idx}.py').read_bytes()
    if SECRET.search(code):raise ValueError('credential shape')
    print(code.decode())
