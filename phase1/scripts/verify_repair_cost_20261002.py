"""Second action census and crosscheck against previously published run receipts."""
import csv,hashlib,json,math,statistics
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');OUT=B/'repair-cost-opportunity-20261002-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    p=read(OUT/'plan.json');s=read(OUT/'summary.json');rr=rows(OUT/'rows.csv');binding=read(OUT/'bindings.private.json')
    assert sha(OUT/'plan.json')==s['plan_sha256'] and sha(OUT/'rows.csv')==s['rows_sha256'] and sha(OUT/'bindings.private.json')==s['bindings_sha256']
    for path,h in binding.items():assert sha(Path(path))==h
    missing=[];verified=[]
    for r in rr:
        root=B/r['batch'];ep=root/f'episode-{r["index"]}'
        receipts=[(int(path.parent.name.split('-')[1]),read(path)) for path in ep.glob('action-*/result.json')]
        follow=[obj for step,obj in receipts if step>0]
        initial=math.fsum(obj['exec_seconds'] for step,obj in receipts if step==0)
        good=math.fsum(obj['exec_seconds'] for obj in follow if obj['valid'])
        bad=math.fsum(obj['exec_seconds'] for obj in follow if not obj['valid'])
        gen=math.fsum(read(path)['generation_seconds'] for path in ep.glob('action-*/generation.private.json'))
        for key,value in [('initial_execution_seconds',initial),('valid_execution_seconds',good),('invalid_execution_seconds',bad),('generation_seconds',gen)]:
            assert math.isclose(float(r[key]),value,rel_tol=1e-12,abs_tol=1e-10)
        assert len(follow)==int(r['returned_followups'])
        assert sum(bool(obj['valid']) for obj in follow)==int(r['valid_followups'])
        # Count prepared generation attempts, not only explicit timeout files.
        n=sum(not (f.parent/'generation.private.json').exists() for f in ep.glob('action-*/feedback.json'))
        if n:missing.append(dict(batch=r['batch'],index=int(r['index']),task=r['task'],arm=r['arm'],prepared_without_generation_receipt=n))
        count=int(r['generation_completed']);denom=gen+good+bad
        assert math.isclose(float(r['generation_fraction_recorded']),gen/denom,abs_tol=1e-12)
        assert math.isclose(float(r['perfect_invalid_reject_fraction_recorded']),bad/denom,abs_tol=1e-12)
        assert math.isclose(float(r['max_average_gate_seconds_per_completed_generation']),bad/count,abs_tol=1e-12)
        verified.append(r)
    # Only component-accounting bounds. Output no projected improvement.
    out=dict(status='PASS_WITH_CENSORING_CLARIFICATION',episodes=len(verified),bindings=len(binding),
        plan_sha256=sha(OUT/'plan.json'),summary_sha256=sha(OUT/'summary.json'),source_sha256=sha(Path(__file__)),
        prepared_without_generation_receipt=missing,
        correction='Producer generation_unfinished counts explicit generation_failed.json only. It does not count all attempts lacking a completion; use this verifier supplement. Source timings and metric summaries unchanged.',
        limitation='An ideal invalid-reject timing ceiling on recorded actions is not actual wall-clock/GPU savings or an efficacy result.')
    with (OUT/'verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
