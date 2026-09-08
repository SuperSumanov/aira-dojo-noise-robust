"""New launcher/worker integration with fake Slurm identity and harmless CPU children.

No srun/sbatch/scancel is executed. This does not validate Slurm enforcement or GPUs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dojo-root', type=Path, required=True)
    parser.add_argument('--plan-root', type=Path, required=True)
    parser.add_argument('--source-tree', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    os.environ.update(CUDA_VISIBLE_DEVICES='', LITELLM_LOCAL_MODEL_COST_MAP='True',
        PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        LOGGING_DIR='/tmp', DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu',
        DEFAULT_SLURM_QOS='gpu', MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread',
        SLURM_JOB_ID='123456789', SLURM_STEP_ID='0', PYTHONPATH=str(args.dojo_root/'src'))
    os.environ.pop('FORETS_RUN_BUDGET_PATH', None)
    os.chdir(args.dojo_root)
    sys.path[:0] = [str(args.dojo_root/'src'), str(args.plan_root)]
    checks, evidence = [], {}
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
        from dojo.config_dataclasses.launcher.srun_pool import SrunPoolConfig
        from dojo.core.runners.slurm.srun_pool import SrunPoolLauncher
        import dojo.core.runners.slurm.srun_pool as pool_module
        from dojo.main_bounded_srun_worker import run_worker
        from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
        from forets_pilot_plan import overrides, bounded_launcher_overrides, run_order
        from hydra import compose, initialize_config_dir
        from hydra.utils import instantiate
        from omegaconf import OmegaConf
        register_new_resolvers()
        hashes = []
        for task, seed, policy in run_order():
            values = overrides(task, seed, policy, max_output_tokens=8192, request_timeout_seconds=120)
            values += bounded_launcher_overrides(max_api_attempts=40, max_output_tokens=8192)
            with initialize_config_dir(config_dir=str(args.dojo_root/'src/dojo/configs'), version_base=None):
                config = compose(config_name='default_runner', overrides=values)
            cfg = instantiate(config.launcher)
            cfg.validate()
            plain = OmegaConf.to_container(config, resolve=True)
            assert plain['logger']['write_env_vars'] is False
            assert cfg.min_remaining_seconds_to_launch == 2130
            del plain['solver']['selection_policy']
            hashes.append(hashlib.sha256(json.dumps(plain, sort_keys=True).encode()).hexdigest())
        assert all(hashes[i] == hashes[i+1] for i in range(0, 8, 2))
        checks.append('full_bounded_launcher_config_pairs_only_selector_differs')
        evidence['paired_config_sha256'] = hashes[::2]

        for change in ({'max_retries':1}, {'step_time_limit_minutes':None},
                       {'worker_wall_seconds':1800}, {'min_remaining_seconds_to_launch':1800},
                       {'forets_max_api_attempts':True}, {'step_termination_allowance_seconds':0}):
            from dataclasses import replace
            try:
                replace(cfg, **change).validate()
                raise AssertionError('invalid launch accepted')
            except ValueError:
                pass
        checks.append('partial_limits_retry_and_missing_cleanup_allowance_rejected')

        with tempfile.TemporaryDirectory(prefix='forets-worker-check-', dir='/tmp') as tmp:
            root = Path(tmp)
            launcher = SrunPoolLauncher.__new__(SrunPoolLauncher)
            launcher.cfg = cfg
            launcher.allocation = NS(job_id='123456789')
            launcher.snapshot_path = args.dojo_root
            launcher.python_executable = Path(sys.executable)
            launcher.log_dir = launcher.identity_dir = root
            launcher.manifest = {'tasks': {'artificial': {'attempt':0, 'attempts':[], 'config_path':str(root/'config.json')}}}
            launcher._save_manifest = Mock()
            with patch.object(pool_module.subprocess, 'Popen', return_value=NS(pid=123)) as spawn:
                launcher._launch('artificial')
            command = spawn.call_args.args[0]
            assert '--time=30' in command and '--kill-on-bad-exit=1' in command
            assert 'dojo.main_bounded_srun_worker' in command
            assert command[command.index('--max-api-attempts')+1] == '40'
            assert command[command.index('--wall-seconds')+1] == '1740'
            with patch.object(pool_module.subprocess, 'Popen') as forbidden_replay:
                try:
                    launcher._launch('artificial')
                    raise AssertionError('bounded controller replay accepted')
                except RuntimeError:
                    pass
                assert forbidden_replay.call_count == 0
            launcher._remaining_seconds = lambda: None
            assert not launcher._can_launch()
            launcher._remaining_seconds = lambda: 2129
            assert not launcher._can_launch()
            launcher._remaining_seconds = lambda: 2130
            assert launcher._can_launch()
            checks.append('actual_launch_argv_has_step_time_and_worker_limits_no_slurm_dispatch')
            evidence['launch_argv_without_paths'] = ['srun','--time=30','--kill-on-bad-exit=1',
                'dojo.main_bounded_srun_worker','--wall-seconds','1740','--max-api-attempts','40']
            launcher.cfg = SrunPoolConfig()
            assert not any(arg.startswith('--time=') for arg in launcher._srun_prefix(job_name='fixture'))
            launcher._remaining_seconds = lambda: None
            assert launcher._can_launch()
            checks.append('unbounded_default_prefix_and_unknown_endtime_behavior_unchanged')

            config_path = root/'config.json'
            config_path.write_text(json.dumps({'logger':{'write_env_vars':False}}))
            def inputs(name, wall=8):
                return NS(config=config_path, identity=root/(name+'.json'), run_id=name, attempt=1,
                          wall_seconds=wall, max_api_attempts=2, max_output_tokens=32)
            child = ('import os,uuid,sys; from dojo.utils.run_budget import reserve; '
                     'assert "litellm" not in sys.modules and "torch" not in sys.modules; '
                     'reserve(os.environ["FORETS_RUN_BUDGET_PATH"],uuid.uuid4().hex,32); ')
            a = inputs('complete')
            code = run_worker(a, worker_command=[sys.executable,'-c',child+'print("artificial")'])
            if code != 0:
                diagnostic = dict(status='FAIL', stage='harmless_child', checks_completed=checks,
                    worker=json.loads((root/'complete.bounded/finished.json').read_text()),
                    process=json.loads((root/'complete.bounded/execution/summary.json').read_text()))
                args.output.write_text(json.dumps(diagnostic, indent=2)+'\n')
                print(json.dumps(diagnostic))
                raise AssertionError('harmless child did not complete; structural diagnostic retained')
            receipt = json.loads((root/'complete.bounded/finished.json').read_text())
            assert receipt['budget_archived'] and receipt['reserved_adapter_attempts'] == 1
            assert receipt['api_cost_usd'] is None
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(root/'complete.bounded/attempts.sqlite')) as db:
                assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 1
            try:
                run_worker(a, worker_command=[sys.executable,'-c','raise SystemExit(99)'])
                raise AssertionError('repeat worker reset budget')
            except FileExistsError:
                pass
            assert 'FORETS_RUN_BUDGET_PATH' not in os.environ
            checks.append('real_cpu_child_gets_private_budget_archival_and_repeat_claim_rejected')

            b = inputs('deadline', wall=1)
            assert run_worker(b, worker_command=[sys.executable,'-c',child+'import time; time.sleep(30)']) == 1
            receipt = json.loads((root/'deadline.bounded/finished.json').read_text())
            assert receipt['budget_archived'] and receipt['worker_status'] == 'timed_out'
            assert receipt['reserved_adapter_attempts'] == 1
            checks.append('timed_out_cpu_child_keeps_dispatch_reservation_and_archives_budget')
            config_path.write_text(json.dumps({'logger':{'write_env_vars':True}}))
            try:
                run_worker(inputs('env_export'), worker_command=[sys.executable,'-c','raise SystemExit(99)'])
                raise AssertionError('environment export allowed')
            except RuntimeError:
                pass
            assert not (root/'env_export.bounded').exists()
            checks.append('environment_export_rejected_before_worker_start')

    result = dict(status='PASS', source_tree=args.source_tree, checks=checks, evidence=evidence,
        real_slurm_dispatches=0, external_api_requests=0, gpu_jobs=0, model_loads=0,
        protected_data_read=False, note='fake Slurm identity, actual harmless local child processes; no cluster enforcement proof')
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
