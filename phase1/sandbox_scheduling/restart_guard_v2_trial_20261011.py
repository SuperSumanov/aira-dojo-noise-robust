"""Independent twelve-case trial of complete restart-aware failure lifecycle."""
import json,os,shutil,subprocess,sys
from pathlib import Path
import restart_guard_trial_20261011 as base
from kernel_shutdown_guard import METHOD_SHA

DONOR=base.ROOT
PIN='47f008933f0bb055bf26d1866444ff074eafb8f950b281d32b8340ada2024f62'
ROOT=base.d.BASE/'resource-restart-guard-trial-20261011-v2'
NAME=Path(__file__).name
base.ROOT=ROOT;base.NAME=NAME;base.d.ROOT=ROOT

def prepare():
    d=base.d
    assert d.sha(DONOR/'plan.json')==PIN
    p=json.loads((DONOR/'plan.json').read_text())
    assert all(d.sha(DONOR/n)==h for n,h in p['files'].items())
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        target=ROOT/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,target)
    for n in (NAME,'kernel_shutdown_guard.py'):
        shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    for row in base.schedule():
        obs=ROOT/f"case-{row['index']}"/'observer'
        if row['arm']=='guard':
            shutil.copyfile(ROOT/'kernel_shutdown_guard.py',obs/'kernel_shutdown_guard.py')
            (obs/'sitecustomize.py').write_text(base.SITE+'    import kernel_shutdown_guard\n')
    batch=(ROOT/'run.sbatch').read_text().replace(str(DONOR),str(ROOT)).replace('#SBATCH --job-name=restart-guard-trial','#SBATCH --job-name=restart-guard-v2').replace('restart_guard_trial_20261011.py',NAME)
    assert str(ROOT/NAME) in batch and str(DONOR) not in batch
    (ROOT/'run.sbatch').write_text(batch)
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    for arm in ('old','guard'):
        subprocess.run([str(d.PY),'-B',str(ROOT/NAME),'preflight',arm],check=True)
    p.update(donor_plan_sha256=PIN,version=2,shutdown_original_method_sha256=METHOD_SHA,
        only_change='Restart-aware failure lifecycle: report parentless restarting/dead as failure and await the in-progress gateway ready future before deletion, bounded15s. No task replay,original image unchanged.',
        question='Does complete restart-aware lifecycle preserve normal output, expose lost state promptly and clean up without HTTP500 or forced server kill?',
        previous_batch='17568:12planned,4attempted,3complete; guard detected actual restart but cleanup raised InvalidStateError/HTTP500,old batch remains failed.',
        expected='12/12 expected terminal cases;6normal identical stdout;3old exit timeouts;3guard non-timeout failure<=8s;all6native exit17 observed;no HTTP500,forced server kill or lingering owned processes.',
        files={str(f.relative_to(ROOT)):d.sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    d.write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,root=str(ROOT),planned=12,plan_sha256=d.sha(ROOT/'plan.json'),gpu_seconds_cap=600)))

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        base.configure(sys.argv[2])
        import inspect
        from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
        assert ('gateway lifecycle event' in inspect.getsource(JupyterKernelClient.execute))==(sys.argv[2]=='guard')
        print(json.dumps(dict(arm=sys.argv[2],imports_pass=True,no_kernel=True)))
    elif sys.argv[1]=='worker':sys.exit(base.worker(int(sys.argv[2])))
    elif sys.argv[1]=='controller':sys.exit(base.controller())
