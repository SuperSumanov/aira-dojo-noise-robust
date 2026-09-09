"""Exercise new campaign wiring with real RunConfigs and fake Slurm/service.

Never loads a model, dispatches Slurm, reads task data or calls an external API.
This is not evidence that two real Slurm steps coexist or that critic helps.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0,str(args.code))
    import forets_e2e_campaign as campaign
    from forets_e2e_package import SOURCE, write_new
    for key in tuple(os.environ):
        if key.startswith('PRIMARY_KEY') or key in ('OPENROUTER_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(key)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', CUDA_VISIBLE_DEVICES='',
        LOGGING_DIR='/tmp', MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu',
        LITELLM_LOCAL_MODEL_COST_MAP='True')
    sys.path.insert(0,str(SOURCE/'src'))
    checks=[]
    with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
        original, configs=campaign.validate_inputs(args.package)
        assert len(configs)==8
        checks.append('actual_eight_worker_configs_and_order_verified')
        for approved, checked, env in [(False,False,{}),(True,False,{}),(True,True,{})]:
            try: campaign.require_execution_ready(approved=approved,route_checked=checked,environment=env)
            except RuntimeError: pass
            else: raise AssertionError('missing gate accepted')
        checks.append('missing_authorization_route_or_credential_refuses_execution')
        identity_env=dict(SLURM_JOB_ID='987654321', OPENROUTER_API_KEY='sk-'+'or-'+'v1-'+'synthetic')
        for step in ('','batch'):
            campaign.require_execution_ready(approved=True,route_checked=True,
                environment=dict(identity_env,SLURM_STEP_ID=step))
        try:
            campaign.require_execution_ready(approved=True,route_checked=True,
                environment=dict(identity_env,SLURM_STEP_ID='0'))
        except RuntimeError:pass
        else:raise AssertionError('nested GPU step accepted as controller')
        checks.append('batch_controller_identity_allowed_but_nested_numeric_step_rejected')
        from dojo.core.runners.slurm.srun_pool import SrunPoolLauncher, AllocationInfo
        allocation=AllocationInfo('987654321','projgpu39',1,12,2,datetime.now()+timedelta(minutes=269))
        with tempfile.TemporaryDirectory(prefix='forets-campaign-check-',dir='/tmp') as tmp:
            root=Path(tmp)/'package';root.mkdir();(root/'configs').mkdir();(root/'runs').mkdir()
            rows=[]
            for row,cfg in zip(original['runs'],configs):
                cfg=json.loads(json.dumps(cfg).replace(str(args.package),str(root)))
                sha=write_new(root/'configs'/(row['run_id']+'.json'),cfg)
                rows.append(dict(row,config_sha256=sha))
            write_new(root/'manifest.json',dict(original,runs=rows))
            runtime=json.loads((args.package/'runtime.NOT_CREDENTIALS.json').read_text())
            write_new(root/'runtime.NOT_CREDENTIALS.json',runtime)
            target=root/'configs'/(rows[1]['run_id']+'.json')
            raw=target.read_bytes()
            changed=json.loads(raw);changed['solver']['step_limit']=5
            # Build an in-memory mismatch with a matching declared hash: the
            # fairness check, not only the byte hash, must catch it.
            changed_raw=(json.dumps(changed,sort_keys=True,indent=2)+'\n').encode()
            target.write_bytes(changed_raw)
            mutant=dict(original,runs=[dict(r) for r in rows])
            mutant['runs'][1]['config_sha256']=hashlib.sha256(changed_raw).hexdigest()
            (root/'manifest.json').write_text(json.dumps(mutant))
            try: campaign.validate_inputs(root)
            except ValueError: pass
            else: raise AssertionError('budget confound accepted')
            target.write_bytes(raw);(root/'manifest.json').write_text(json.dumps(dict(original,runs=rows)))
            checks.append('one_arm_budget_change_rejected_even_with_updated_hash')
            calls=[]
            class FakeService:
                def __init__(self,*a,**kw):
                    calls.append(a[0]);self.code=None
                    write_new(root/'critic.ready.json',dict(allocation_id='987654321',step_id='0',
                        model_load_and_bind_seconds=1.0,visible_gpu='synthetic'))
                def poll(self):return self.code
                def terminate(self):self.code=-15
                def kill(self):self.code=-9
                def wait(self,timeout=None):return self.code
            def fake_run(pool):
                assert pool._can_launch()
                assert len(pool.run_configs)==8
                assert pool.cfg.max_retries==0 and pool.cfg.forets_max_api_attempts==40
                return dict(successful=False,counts={'pending':8},manifest_path=str(pool.manifest_path))
            # Synthetic environment, never a real credential or scheduler identity.
            env=dict(os.environ,SLURM_JOB_ID='987654321')
            env.pop('SLURM_STEP_ID',None)
            env['OPENROUTER_API_KEY']='sk-'+'or-'+'v1-'+'synthetic'
            with patch.dict(os.environ,env,clear=True), \
                 patch.object(campaign,'install_process_credential'), \
                 patch.object(SrunPoolLauncher,'_discover_allocation',return_value=allocation), \
                 patch.object(SrunPoolLauncher,'run',fake_run), \
                 patch.object(campaign.subprocess,'Popen',FakeService), \
                 patch.object(campaign.subprocess,'run',return_value=NS(returncode=0)) as cancel:
                result=campaign.execute(root,approved=True,route_checked=True)
                assert result['status']=='incomplete' and len(calls)==1
                assert '--gres=gpu:1' in calls[0] and '--time=265' in calls[0]
                assert cancel.call_args.args[0]==['scancel','--signal=TERM','987654321.0']
            checks.append('one_service_and_actual_pool_config_mapping_with_fake_scheduler')
            actual=json.loads((root/'runtime-manifest.json').read_text())
            assert len(actual['runs'])==8
            assert all('/srun_pool/' in r['process_summary'] for r in actual['runs'])
            campaign.collect(root)
            readout=json.loads((root/'readout/summary.json').read_text())
            assert readout['planned_runs']==8 and readout['comparable_pairs']==0
            assert all(r['final_score_observed'] is None for r in readout['runs'])
            checks.append('not_started_runs_kept_and_readout_uses_actual_pool_paths')
    result=dict(status='CAMPAIGN_WIRING_CHECK_PASS',checks=checks,actual_gpu_jobs=0,
        model_loads=0,actual_task_runs=0,external_api_calls=0,real_slurm_commands=0,
        limits='Fake service and fake Slurm; no live coallocation, endpoint, model or task execution.',
        campaign_sha256=hashlib.sha256((args.code/'forets_e2e_campaign.py').read_bytes()).hexdigest())
    write_new(args.output,result)
    print(json.dumps(result))


if __name__=='__main__':main()
