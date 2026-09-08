"""Real Linux process tests using harmless artificial workers; no GPU/API."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert os.name == 'posix' and not args.output.exists()
    spec = importlib.util.spec_from_file_location('bounded', args.module)
    bounded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bounded)
    checks = []
    with tempfile.TemporaryDirectory(prefix='forets-wall-check-') as temp:
        root = Path(temp)
        def run(name, code, wall=2.):
            return bounded.run_bounded([sys.executable, '-c', code], cwd=root,
                output_dir=root / name, wall_seconds=wall, grace_seconds=.2,
                environment={'PATH': os.environ['PATH'], 'CUDA_VISIBLE_DEVICES': ''})
        normal = run('normal', 'print("artificial private output")')
        assert normal['status'] == 'completed' and normal['returncode'] == 0
        assert normal['api_cost_usd'] is None and 'artificial private output' not in json.dumps(normal)
        assert (root / 'normal/stdout.private.log').stat().st_mode & 0o777 == 0o600
        checks.append('normal_completion_private_output_unknown_cost')
        failed = run('failed', 'raise SystemExit(7)')
        assert failed['status'] == 'failed' and failed['returncode'] == 7
        checks.append('nonzero_not_success')
        stubborn = run('stubborn', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)', .5)
        assert stubborn['status'] == 'timed_out' and stubborn['returncode'] == -signal.SIGKILL
        assert stubborn['elapsed_seconds'] < 3
        checks.append('hard_timeout_then_kill')
        # Parent exits normally, leaving a same-group child. Cleanup still runs.
        orphan_code = ('import subprocess,sys,pathlib; p=subprocess.Popen([sys.executable,"-c",'
                       '"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"]);'
                       'pathlib.Path("child.pid").write_text(str(p.pid))')
        orphan = run('orphan', orphan_code)
        child = int((root / 'child.pid').read_text())
        def alive(pid):
            try:
                # Zombie is terminated, but may await init reaping.
                return Path('/proc/' + str(pid) + '/stat').read_text().split(') ', 1)[1].split()[0] != 'Z'
            except FileNotFoundError:
                return False
        deadline = time.monotonic() + 2
        while alive(child) and time.monotonic() < deadline:
            time.sleep(.02)
        assert not alive(child) and orphan['status'] == 'completed_with_leftovers'
        checks.append('leader_exit_reclaims_same_group_child')
        try:
            run('normal', 'raise SystemExit(99)')
            raise AssertionError('existing run replay accepted')
        except FileExistsError:
            checks.append('existing_run_refused')
        # Real SIGTERM to supervisor: no broad process targeting.
        worker = [sys.executable, str(args.module.resolve()), '--cwd', str(root), '--output-dir',
                  str(root / 'interrupt'), '--wall-seconds', '20', '--grace-seconds', '.2', '--',
                  sys.executable, '-c', 'import pathlib,os,time; pathlib.Path("interrupt.pid").write_text(str(os.getpid())); time.sleep(30)']
        supervisor = subprocess.Popen(worker, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      env={'PATH': os.environ['PATH'], 'CUDA_VISIBLE_DEVICES': ''})
        try:
            deadline = time.monotonic() + 5
            while not (root / 'interrupt.pid').exists() and time.monotonic() < deadline:
                if supervisor.poll() is not None:
                    raise AssertionError('supervisor exited before worker started')
                time.sleep(.02)
            pid = int((root / 'interrupt.pid').read_text())
            supervisor.terminate()
            assert supervisor.wait(timeout=3) == 1
            result = json.loads((root / 'interrupt/summary.json').read_text())
            assert result['status'] == 'interrupted' and not alive(pid)
            checks.append('supervisor_term_reclaims_worker')
        finally:
            if supervisor.poll() is None:
                supervisor.kill()
                supervisor.wait()
    report = dict(status='CPU_PROCESS_CHECK_PASS', checks=checks, checks_passed=len(checks),
                  gpu_requested=False, api_calls=0, protected_data_read=False,
                  real_task_executed=False, slurm_containment_verified=False,
                  limitation='setsid escape and supervisor SIGKILL require cluster-side cgroups/time limit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
