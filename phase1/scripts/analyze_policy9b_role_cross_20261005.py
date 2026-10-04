"""Pre-run analysis for fixed-input role crossover; no accuracy headline or E2E claim."""
import argparse,csv,hashlib,json,os,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/policy9b-role-cross-20261005-v1')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tally(rows):
    return dict(assigned=len(rows),parsed=sum(r['status']=='parsed' for r in rows),
        missing=sum(r['status']!='parsed' for r in rows),
        valid_denominator=sum(r['objective_valid'] for r in rows),
        invalid_denominator=sum(not r['objective_valid'] for r in rows),
        valid_veto=sum(r['objective_valid'] and r['is_bug'] is True for r in rows),
        invalid_accept=sum(not r['objective_valid'] and r['is_bug'] is False for r in rows))
def main():
    assert read(R/'analysis-freeze.json')['sha256']==sha(Path(__file__))
    plan=read(R/'plan.json');job=read(R/'launch.json')['job'];env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip()
    accounting=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines();assert len(accounting)==1
    jid,state,elapsed,tres,exitcode,*_=accounting[0].split('|');assert jid==job and state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY')) and 'gres/gpu=2' in tres
    for name,h in plan['files'].items():assert sha(R/name)==h
    for name,h in plan['source_files'].items():assert sha(Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')/name)==h
    cases=read(R/'cases.private.json');rows=[]
    for call in plan['calls']:
        case=cases[call['case']];path=R/'records'/f"{call['index']}.json"
        rec=read(path) if path.exists() else dict(status='unattempted',is_bug=None)
        if rec['status']=='parsed':
            private=read(R/'records'/f"{call['index']}.private.json")
            assert type(private['answer']['is_bug']) is bool and private['answer']['is_bug']==rec['is_bug']
            assert rec['prompt_sha256']==case['prompt_sha256']
        rows.append(dict(**call,source_arm=case['source_arm'],objective_valid=case['objective_valid'],
            status=rec['status'],is_bug=rec.get('is_bug'),latency_seconds=rec.get('elapsed_seconds'),
            error_type=rec.get('error_type'),prompt_tokens=rec.get('prompt_tokens'),completion_tokens=rec.get('completion_tokens')))
    assert len(rows)==88
    groups=[];comparisons=[]
    for seed in plan['seeds']:
        cells={arm:tally([r for r in rows if r['seed']==seed and r['arm']==arm]) for arm in ('base','sft')}
        comparisons.append(dict(seed=seed,**cells,qualified=cells['sft']['valid_veto']<cells['base']['valid_veto'] and cells['sft']['invalid_accept']<=cells['base']['invalid_accept'] and cells['sft']['missing']<=cells['base']['missing']))
        for arm in ('base','sft'):
            for task in sorted({r['task'] for r in rows}):groups.append(dict(seed=seed,arm=arm,task=task,**tally([r for r in rows if r['seed']==seed and r['arm']==arm and r['task']==task])))
    cost=2*int(elapsed)/3600
    report=dict(status='CLOSED_POSTHOC_ROLE_CROSSOVER',job=job,state=state,exitcode=exitcode,elapsed_seconds=int(elapsed),
        gpu_hours=cost,window_gpu_hours=cost+plan['window_previous_gpu_hours'],assigned=88,cases=22,source_runs=8,
        comparisons=comparisons,by_task=groups,diagnostic_qualification=all(c['qualified'] for c in comparisons),
        plan_sha256=sha(R/'plan.json'),analysis_sha256=sha(Path(__file__)),
        scope=plan['limitations'],no_automatic_e2e_extension=True)
    out=R/'readout-v1';out.mkdir()
    with (out/'summary.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
    with (out/'calls.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    receipt={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    with (out/'export-receipt.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps(report))
def test():
    cases=[dict(status='parsed',objective_valid=True,is_bug=True),dict(status='parsed',objective_valid=False,is_bug=False),dict(status='failed',objective_valid=True,is_bug=None),dict(status='unattempted',objective_valid=False,is_bug=None)]
    assert tally(cases)==dict(assigned=4,parsed=2,missing=2,valid_denominator=2,invalid_denominator=2,valid_veto=1,invalid_accept=1)
    assert tally([])['missing']==0
    print(json.dumps(dict(status='CPU_PASS',real_model_calls=0,checks=2)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--test',action='store_true');a=p.parse_args();test() if a.test else main()
