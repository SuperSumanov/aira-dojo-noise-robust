"""Fixed literal readiness-failure census; no raw logs/code/env exported."""
import hashlib,json,tarfile
from collections import Counter
from pathlib import PurePosixPath
from read_comparison_qwen_20260919 import ROOT,STRUCTURE_SHA
from discover_comparison_20260919 import SECRET


def text_values(value):
    if isinstance(value,str):return value
    if isinstance(value,list):return '\n'.join(text_values(x) for x in value)
    if isinstance(value,dict):return '\n'.join(text_values(x) for x in value.values())
    return ''


def main():
    structural=(ROOT/'structure.redacted.json').read_bytes()
    if hashlib.sha256(structural).hexdigest()!=STRUCTURE_SHA:raise ValueError('structural identity')
    nodes_raw=(ROOT/'qwen-readout-v1/nodes.json').read_bytes()
    if hashlib.sha256(nodes_raw).hexdigest()!='370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9':raise ValueError('node identity')
    known=json.loads(nodes_raw)
    allowed_nodes={(n['run'],n['id']) for n in known if n['group']=='executed'}
    rows=[];seen=set()
    for archive in json.loads(structural)['archives']:
        allowed={str(PurePosixPath(c['path']).parent):c for c in archive['configs']
                 if c['fields'].get('solver.operators.draft.llm.client.model_id')=='qwen3.8-27b'
                 and c['fields'].get('metadata.launch_time','')[:10]>='2026-09-12'}
        with tarfile.open(ROOT/'archives'/archive['archive'],'r|gz') as tf:
            for member in tf:
                path=PurePosixPath(member.name);rr=str(path.parent.parent)
                if not member.isfile() or path.name!='journal.jsonl' or rr not in allowed:continue
                run=hashlib.sha256(rr.encode()).hexdigest()[:16];nodes=0;markers=[]
                for line in tf.extractfile(member):
                    n=json.loads(SECRET.sub('[REDACTED]',line.decode()));key=(run,n['id'])
                    if key not in allowed_nodes or key in seen:raise ValueError('scope/duplicate')
                    seen.add(key)
                    if not n.get('operators_used'):continue
                    nodes+=1;text=text_values(n.get('term_out'))+'\n'+text_values(n.get('_term_out'))
                    if 'Kernel did not become ready in time.' in text:
                        markers.append(dict(node=n['id'],exec_time=n.get('exec_time'),exit_code=n.get('exit_code'),
                            generic_program_timeout_message='Execution exceeded the time limit' in text,
                            recorded_buggy=n.get('is_buggy')))
                fields=allowed[rr]['fields']
                rows.append(dict(run=run,commit=fields['metadata.git_commit_id'],
                    task=archive['archive'].removesuffix('.tar.gz'),nodes=nodes,readiness_failures=markers))
    if seen!=allowed_nodes:raise ValueError('incomplete census')
    summary=dict(role='runtime_metadata_diagnostic_no_outcome_reclassification',runs=len(rows),
        nonroot_executed_nodes=sum(r['nodes'] for r in rows),
        marker_nodes=sum(len(r['readiness_failures']) for r in rows),
        affected_runs=sum(bool(r['readiness_failures']) for r in rows),
        generic_timeout_messages=sum(x['generic_program_timeout_message'] for r in rows for x in r['readiness_failures']),
        by_task=dict(Counter({t:sum(len(r['readiness_failures']) for r in rows if r['task']==t) for t in {r['task'] for r in rows}})),
        rows=rows,limitation='Exact historical harness marker, not proof every error was transient/recoverable; no failed candidate is dropped or rescored.')
    output=ROOT/'kernel-readiness-census.json'
    with output.open('x') as f:json.dump(summary,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
    print(json.dumps(dict(sha256=hashlib.sha256(output.read_bytes()).hexdigest())))

if __name__=='__main__':main()
