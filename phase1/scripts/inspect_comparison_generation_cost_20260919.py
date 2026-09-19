"""Numeric operator metadata only for the already isolated new-Qwen scope."""
import hashlib,json,re,tarfile
from collections import Counter
from pathlib import Path,PurePosixPath
from read_comparison_qwen_20260919 import ROOT,STRUCTURE_SHA
from discover_comparison_20260919 import SECRET

def numeric_fields(value,prefix=''):
    if isinstance(value,dict):
        for k,v in value.items():
            if re.search(r'(?i)(key|secret|password|authorization|prompt|response|reasoning|completion|content|text)',k):continue
            yield from numeric_fields(v,prefix+'.'+k if prefix else k)
    elif isinstance(value,list):
        for i,v in enumerate(value):yield from numeric_fields(v,prefix+'.'+str(i))
    elif type(value) in (int,float) and re.search(r'(?i)(time|second|duration|latency|cost|token)',prefix):
        yield prefix,value

def main():
    raw=(ROOT/'structure.redacted.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==STRUCTURE_SHA
    rows=[];schemas=Counter()
    for archive in json.loads(raw)['archives']:
        allowed={str(PurePosixPath(c['path']).parent):c for c in archive['configs']
            if c['fields'].get('solver.operators.draft.llm.client.model_id')=='qwen3.8-27b'
            and c['fields'].get('metadata.launch_time','')[:10]>='2026-09-12'}
        if not allowed:continue
        with tarfile.open(ROOT/'archives'/archive['archive'],'r|gz') as tf:
            for member in tf:
                path=PurePosixPath(member.name);runroot=str(path.parent.parent)
                if not member.isfile() or path.name not in ('journal.jsonl','journal_for_unselected.jsonl') or runroot not in allowed:continue
                for line in tf.extractfile(member):
                    n=json.loads(SECRET.sub(b'[REDACTED]',line) if isinstance(SECRET.pattern,bytes) else SECRET.sub('[REDACTED]',line.decode()))
                    fields=dict(numeric_fields(n.get('operators_metrics',[])))
                    schemas[tuple(sorted(fields))]+=1
                    rows.append(dict(run=hashlib.sha256(runroot.encode()).hexdigest()[:16],node=n.get('id'),
                        group='executed' if path.name=='journal.jsonl' else 'unselected',operators=n.get('operators_used'),
                        numeric_operator_fields=fields))
    out=ROOT/'operator-cost-metadata.json'
    with out.open('x') as h:json.dump(rows,h,indent=2,allow_nan=False)
    print(json.dumps(dict(status='NUMERIC_METADATA_ONLY',rows=len(rows),
        schemas=[dict(fields=list(k),nodes=v) for k,v in schemas.items()],examples=[r for r in rows if r['numeric_operator_fields']][:2],
        sha256=hashlib.sha256(out.read_bytes()).hexdigest())),flush=True)

if __name__=='__main__':main()
