"""Real production hooks and signal handling, with installed quota inspected."""
import argparse,hashlib,inspect,json,subprocess,sys
from pathlib import Path
import colocation_production_gate_20261016 as gate

def configure():
    s=inspect.getsource(gate.exercise)
    s=s.replace('import colocation_trial_20261016 as trial','import generation_quota_trial_20261017 as trial')
    needle='            trial.install_hooks(row,ep,deadline)'
    replacement='''            import live_runtime_hooks as hooks
            with patch.object(hooks,'wait_for_ready',lambda *a,**kw:False):
                actual=trial.runtime_hook_guard()
                actual.install_hooks(row,ep,deadline)
            import feedback_parent_policy_20261012 as parent
            assert parent.select_request.quota_mode==row['quota_mode']
            fixture_state=dict(active=[dict(task='fixture'),dict(task='fixture')],
                waiting=[dict(key='third',task='fixture',role='analyze',requested=0,run=0)])
            selected,_=parent.select_request(fixture_state,'fixture','greedy')
            assert selected==('third' if row['quota_mode']=='pooled' else None)
            from clock_pairing_20261016 import InfrastructureReadinessError
            try:JupyterKernelClient.wait_for_ready(None)
            except InfrastructureReadinessError:pass
            else:raise AssertionError('production readiness failure not propagated')'''
    assert s.count(needle)==1;s=s.replace(needle,replacement)
    exec(compile(s,'actual-quota-production-gate','exec'),gate.__dict__)

def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--index',type=int);p.add_argument('--case',choices=gate.CASES)
    a=p.parse_args();configure()
    if a.case:print(json.dumps(gate.exercise(a.root,a.index,a.case),sort_keys=True));return
    rows=[]
    for index in (0,8):
        for case in gate.CASES:
            cp=subprocess.run([sys.executable,'-B',__file__,str(a.root),'--index',str(index),'--case',case],capture_output=True,text=True,timeout=60)
            if cp.returncode:
                with (a.root/f'production-gate-{index}-{case}.private.log').open('x') as f:f.write(cp.stdout+cp.stderr)
                raise RuntimeError(f'production gate failed index={index},case={case}')
            row=json.loads(cp.stdout.splitlines()[-1]);assert row['passed'];rows.append(row)
    result=dict(passed=True,cases=rows,production_source_sha256=hashlib.sha256((a.root/'generation_quota_trial_20261017.py').read_bytes()).hexdigest(),
        interpretation='CPU native-host dispatch/readiness/transaction tests only. Direct facade calls are insufficient; sealed19004 is not rerun or reclassified. No CUDA or search benefit.')
    with (a.root/'production-guard.safe.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps(dict(passed=True,production_cases=len(rows),gpu_calls=0,model_calls=0)))

if __name__=='__main__':main()
