"""Comparison archive metadata and source; no journal values or env files."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from discover_comparison_20260919 import safe_text, SECRET

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'comparison-quarantine-20260919-_tda9fh6'
MANIFEST_SHA='d2e9f41bc697651d266a2574f7b9d4a2d7e474c3851b92d504763e9b535c80cb'
HEAD='54e8a0e3458e12443658104d244e2b6d9e553451'
KEEP=re.compile(r'(^id$|^task\.|seed$|git_commit_id$|launch_time$|time_limit_secs$|execution_timeout$|step_limit$|model_id$|model_name$|checkpoint|model_path$|_target_$|num_candidates$|num_children$|top_k$|temperature$|top_p$|hardware$|device$|num_gpus$|max_model_len$|parallel|candidate|n_generate|n_select|n_execute)',re.I)

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()

def flatten(obj,prefix=''):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if re.search(r'(?i)(key|secret|token|password|authorization|env)',k):continue
            yield from flatten(v,prefix+'.'+k if prefix else k)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from flatten(v,prefix+'.'+str(i))
    elif KEEP.search(prefix) and (obj is None or isinstance(obj,(str,int,float,bool))):
        yield prefix,safe_text(str(obj)) if isinstance(obj,str) else obj

def main():
    os.umask(0o077)
    manifest=ROOT/'manifest.private.json'
    if sha(manifest)!=MANIFEST_SHA:raise ValueError('manifest changed')
    records=[]
    for row in json.loads(manifest.read_bytes())['records']:
        path=ROOT/'archives'/row['name']
        if sha(path)!=row['sha256']:raise ValueError('archive changed')
        configs=[];members=[];names=set()
        with tarfile.open(path,'r|gz') as tf:
            for m in tf:
                p=PurePosixPath(m.name)
                if p.is_absolute() or '..' in p.parts or m.name in names:raise ValueError('unsafe or duplicate member')
                names.add(m.name)
                if len(names)>100000:raise ValueError('member cap')
                if not m.isfile():continue
                if p.name in ('journal.jsonl','journal_for_unselected.jsonl','state.json','JOURNAL.jsonl'):
                    members.append({'path':m.name,'bytes':m.size})  # No payload opened.
                if p.name=='dojo_config.json':
                    if m.size>2*1024**2:raise ValueError('config cap')
                    raw=tf.extractfile(m).read()
                    clean=SECRET.sub('[REDACTED_SECRET]',raw.decode())
                    obj=json.loads(clean)
                    configs.append({'path':m.name,'sha256':hashlib.sha256(raw).hexdigest(),
                        'credential_hits':len(SECRET.findall(raw.decode())), 'fields':dict(flatten(obj))})
        records.append({'archive':row['name'],'configs':configs,'members':members,'tar_members':len(names)})
        print(json.dumps({'archive':row['name'],'configs':len(configs),'checkpoints':dict(Counter(PurePosixPath(x['path']).name for x in members)),
                          'config_example':configs[:1]},ensure_ascii=False),flush=True)
    payload={'utc':datetime.now(timezone.utc).isoformat(),'archives':records,'journal_values_read':False}
    with (ROOT/'structure.redacted.json').open('x') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    source='src/dojo/analysis_utils/journal_to_fig.py'
    raw=subprocess.check_output(['git','-C',str(BASE/'aira-dojo'),'show',HEAD+':'+source],stderr=subprocess.PIPE)
    clean=safe_text(raw.decode())
    with (ROOT/'journal_to_fig.redacted.py.txt').open('x') as f:f.write(clean)
    print(json.dumps({'status':'STRUCTURE_COMPLETE','root':str(ROOT),'runs':sum(len(x['configs']) for x in records),
        'structure_sha256':sha(ROOT/'structure.redacted.json'),'analysis_source_sha256':hashlib.sha256(raw).hexdigest(),
        'analysis_source_credential_hits':len(SECRET.findall(raw.decode()))}),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'STRUCTURE_FAILED','error_type':type(exc).__name__}),flush=True)
        raise SystemExit(2)
