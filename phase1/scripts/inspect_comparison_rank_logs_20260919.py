"""Metadata/strict numeric-log inspection of already isolated new Qwen runs.

Never exports code, prompts, raw log lines, credentials, or older API run values.
This locates rank evidence, not an inferred candidate-to-score association.
"""
import hashlib,json,os,signal,tarfile
from collections import Counter
from pathlib import PurePosixPath
from read_comparison_qwen_20260919 import ROOT,STRUCTURE_SHA

def main():
    os.umask(0o077)
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(300)
    raw=(ROOT/'structure.redacted.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==STRUCTURE_SHA
    records=[];all_names=Counter();parent_names=Counter()
    for archive in json.loads(raw)['archives']:
        allowed={str(PurePosixPath(c['path']).parent) for c in archive['configs']
                 if c['fields'].get('solver.operators.draft.llm.client.model_id')=='qwen3.8-27b'
                 and c['fields'].get('metadata.launch_time','')[:10]>='2026-09-12'}
        if not allowed:continue
        with tarfile.open(ROOT/'archives'/archive['archive'],'r|gz') as tf:
            for member in tf:
                if not member.isfile():continue
                root=next((p for p in allowed if member.name.startswith(p+'/')),None)
                if root is None:continue
                relative=member.name[len(root)+1:]
                all_names[PurePosixPath(relative).name]+=1
                parent_names[str(PurePosixPath(relative).parent)]+=1
                if not (relative.endswith('.log') or relative.endswith('.txt')):continue
                # Filename/size only first; env and arbitrary artifacts never opened.
                records.append(dict(run=hashlib.sha256(root.encode()).hexdigest()[:16],
                    relative_path=relative,bytes=member.size))
    result=dict(log_files=records,all_basenames=dict(all_names),parent_paths=dict(parent_names))
    out=ROOT/'rank-log-inventory-v2.json'
    with out.open('x') as handle:json.dump(result,handle,indent=2)
    print(json.dumps({'status':'LOG_INVENTORY_ONLY','files':len(records),
        'basenames':dict(Counter(PurePosixPath(x['relative_path']).name for x in records)),
        'all_basenames':dict(all_names),'parent_paths':dict(parent_names),
        'examples':records[:12],'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'FAILED','error_type':type(exc).__name__}),flush=True)
        raise SystemExit(2)
