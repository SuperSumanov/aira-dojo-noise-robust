"""Post-closure, CPU-only response audit; never executes recovered code.

The permissive extraction is descriptive, not a replacement scoring protocol.
No new generations, labels, predictions, or root replacements.
"""
import ast,collections,difflib,hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v4')
PLAN='a638e6be539955577950714bcf700c8104babca940e1478a41941ff0e8a098dd'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    raw=p.read_bytes();assert not SECRET.search(raw),'credential shape'
    return json.loads(raw)
def main():
    assert sha(R/'plan.json')==PLAN and read(R/'closed.json')['service_closed']
    assert read(R/'readout-v1/verification.json')['status']=='PASS'
    rows=[];files={};history=[]
    for s in read(R/'plan.json')['schedule']:
        if s['role']!='root':continue
        prior=[]
        for step in range(1,5):
            d=R/f'episode-{s["index"]}/action-{step}'
            if not (d/'generation.private.json').exists():continue
            g=read(d/'generation.private.json');raw=g['response'];q=read(d/'request.private.json');f=read(d/'format.json')
            fence=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
            tool=re.findall(r'<parameter=code>\s*(.*?)\s*</parameter>',raw,re.S)
            codes=fence+tool;parses=[];submissions=[];calls=[]
            for code in codes:
                try:t=ast.parse(code)
                except SyntaxError:parses.append(False);continue
                parses.append(True)
                names=[ast.unparse(n.func) for n in ast.walk(t) if isinstance(n,ast.Call)];calls+=names
                submissions.append(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('to_csv','write_csv','savetxt') for n in ast.walk(t)))
            modes=re.findall(r'(?m)^\s*(PLAN|CHECK|SOLUTION)\s*$',raw.split('```',1)[0]);usage=g.get('usage',{})
            usage={k:v for k,v in usage.items() if isinstance(v,(int,float,bool))}
            item=dict(index=s['index'],task=s['task'],step=step,format=f['status'],accepted_mode=f.get('mode'),mode_lines=modes,python_fences=len(fence),native_tool_code_blocks=len(tool),parseable_blocks=sum(parses),csv_writer_blocks=sum(submissions),
                started=(d/'started.json').exists(),returned=(d/'result.json').exists(),generation_seconds=g['generation_seconds'],usage=usage,response_chars=len(raw),prompt_chars=len(q['prompt']),
                response_sha256=hashlib.sha256(raw.encode()).hexdigest(),max_similarity_to_prior_response=max((difflib.SequenceMatcher(None,raw,z,autojunk=False).ratio() for z in prior),default=None),
                code_call_signatures=sorted(set(calls)))
            prior.append(raw);rows.append(item)
            for name in ('generation.private.json','request.private.json','format.json'):files[str((d/name).relative_to(R))]=sha(d/name)
    summary=read(R/'readout-v1/summary.json')
    result=dict(status='CLOSED_DESCRIPTIVE_PROTOCOL_AUDIT',plan_sha256=PLAN,summary_sha256=sha(R/'readout-v1/summary.json'),rows=rows,input_hashes=files,
        counts=dict(responses=len(rows),accepted_plans=sum(r['accepted_mode']=='PLAN' for r in rows),format_rejections=sum(r['format']=='REJECT' for r in rows),executions_started=sum(r['started'] for r in rows),parseable_code_blocks=sum(r['parseable_blocks'] for r in rows),csv_writer_blocks=sum(r['csv_writer_blocks'] for r in rows)),
        interpretation='No recovered code is executed. Parseability is not a valid submission. Zero obvious CSV writers is a static descriptive check, not general proof of all possible side effects. Unstarted comparisons remain unknown, not zero gain.',
        method_tested=any(r['role']=='comparison' and r['launched'] for r in summary['runs']))
    with (R/'readout-v1/protocol-audit.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k!='input_hashes'}))
if __name__=='__main__':main()
