"""Two never-executed source variants, full public fixture, strong reference.

CNN32 with original augmentation and UNet3Residual; no source/hparam changes.
Both initialise in parallel: candidate-serial versus share2, three restarts.
Same tasks/families from public parent-child traces: not independent new tasks.
"""
import argparse
import ast
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import neural_overlap_control as c
from lifecycle_pilot import read,write,sha

R=Path('/research/d7/spc/yzyang4/scheduling-neural-extension-20261010-v1')
D=R.parent/'scheduling-neural-full-confirmation-20261008-v1'
DONOR='b8bf8619c61a98db5af35bb2b68f4b9838354c9ccfef166d8dd788ca0b16df7f'
NAME='neural_extension_20261010.py'
PINS=(('aerial-cactus-identification','ea47bb6d4ec1601cd59a0904a434596cda54d673ce93d4a21e79995aaf0db36f'),
      ('denoising-dirty-documents','c60e3f1cc3b4613a9707f1c86df12d6d45f1ef36a48ee858b768f9cc8806598d'))
CAP=5400
ORIGINAL_WORKER=inspect.getsource(c.n.worker)
ORIGINAL_RUN_ONE=inspect.getsource(c.n.run_one)
ORIGINAL_CONTROLLER=inspect.getsource(c.n.controller)
ORIGINAL_WAIT=inspect.getsource(c.wait_turn)


def rewritten_worker():
    source=ORIGINAL_WORKER
    replacements=[('else 525','else 1080'),('ji._slurm_gateway_port=', 'ji._gateway_port=')]
    for before,after in replacements:
        if source.count(before)!=1:raise ValueError('worker interface drift')
        source=source.replace(before,after)
    return source


def configure():
    scope();p=c.r.configure()
    # Queue inside the whole allocation, not inside the 450s candidate budget.
    # Extra worker allowance accommodates one 450s predecessor, initialization,
    # its own 450s candidate and bounded cleanup. Both policies get it.
    exec(compile(rewritten_worker(),'extension-worker','exec'),c.n.__dict__)
    source=ORIGINAL_RUN_ONE
    if source.count('else 550')!=1:raise ValueError('supervisor interface drift')
    exec(compile(source.replace('else 550','else 1120'),'extension-supervisor','exec'),c.n.__dict__)
    if ORIGINAL_CONTROLLER.count('math.ceil(2/width)*555')!=1 or ORIGINAL_WAIT.count('>450')!=1:
        raise ValueError('whole-block/queue allowance interface')
    exec(compile(ORIGINAL_CONTROLLER.replace('math.ceil(2/width)*555','1125'),'extension-controller','exec'),c.n.__dict__)
    exec(compile(ORIGINAL_WAIT.replace('>450','>600'),'extension-queue','exec'),c.__dict__)
    return p


def sources(root):
    import census as census
    rows=json.loads(census.read_pinned(census.SAMPLE,'11b3f7c9c28119b612f332af6b6ddfc6fabd02a4f7694912576e615871ed8039'))['selected']
    wanted=dict(PINS);found={}
    for filename,pin in census.PINS.items():
        selected=[r for r in rows if r['file']==filename and r['task'] in wanted]
        if not selected:continue
        obj=json.loads(census.read_pinned(census.ROOT/filename,pin))
        for row in selected:
            for code in census.get_pair(obj,row):
                if census.sha(code.encode())==wanted[row['task']]:found[row['task']]=code
    if set(found)!=set(wanted):raise ValueError('fixed new source missing')
    from throughput_pilot import code_safe
    for i,(task,pin) in enumerate(PINS):
        raw=found[task].encode();code_safe(raw)
        # Only the fresh not-yet-frozen preparation root is changed here.
        (root/f'programs/{i}.py').write_bytes(raw)
    return None


def mutate(plan):
    c.mutate_plan(plan)
    plan.update(question='Does full-execution overlap beat startup-only overlap for these two new frozen original program variants on full public inputs?',
        candidate_worker_AST_unchanged=False,
        worker_changes='only 525->1080s outer deadline and actual gateway-port hook; 450s candidate, original source/hparams, common new queue allowance',
        interpreter_deadline_seconds=1080,worker_hard_seconds=1120,barrier_wait_cap_seconds=600,whole_next_block_reserve_seconds=1125,
        donor_programs_replaced=True,not_independent_new_tasks=True,
        source_selection='One previously unexecuted from-scratch CNN32 augmentation variant and one UNet3Residual variant, fixed by source/dependencies before performance.',
        no_own_concurrent_heavy_preparation=True,input_scale='exact full-input donor; source-defined subset and internal validation unchanged',
        decision='all12 complete; all3 paired pool blocks; equal optimizer steps per source; original output-difference tolerance; median pipeline/share2>=1.05; all failures retained, no replacement',
        new_window_cost_cap_gpu_hours=2.25)
    for key in ('independent_confirmation_not_replacement','original_per_candidate_and_worker_limits_unchanged','qualification'):
        plan.pop(key,None)
    for i,(task,pin) in enumerate(PINS):
        plan['programs'][i].update(task=task,source_sha256=pin,data=str(R/f'data-{i}'))
    plan['preflight_items'].update(fixed_sample='new two source pins fixed preexecution, three original-seed restarts per arm; related to historical public program families',
        distribution='same two tasks, new program variants; not cross-task generalization or independent training seeds',
        walltime='one3090/6CPU/90min all-in; candidate450s, worker1120s incl queue, fixed12; no retries/extension',
        power='limited systems extension; output invariance on fixed query not full quality guarantee')


def batch_script(original):
    if str(D) not in original or 'neural_full_confirmation.py controller' not in original:
        raise ValueError('donor batch interface')
    return original.replace(str(D),str(R)).replace('neural_full_confirmation.py controller',NAME+' controller').replace(
        'r14-neural-confirm','r14-neural-extension').replace('--time=00:45:00','--time=01:30:00').replace('2660s srun','5350s srun')


def scope():
    c.R=R;c.set_scope()
    r=c.r;r.R=R;r.D=D;r.DONOR=DONOR;r.NAME=NAME;r.NODE='gpu27';r.CAP=CAP
    r.JOBNAME='r14-neural-extension';r.FIXTURE_BUILDER=sources;r.PLAN_MUTATOR=mutate
    r.QUESTION='Fixed two new program variants: full-input pipeline/share2.'
    r.EXTRA_FILES=('neural_full_input_trial.py','neural_overlap_control.py','bounded_readiness.py','test_neural_extension.py')
    r.batch_script=batch_script


def prepare(commit):
    scope();c.r.prepare(commit)
    # CPU-only source imports in the exact existing image; never execute main.
    p=configure();m=p.runtime()
    from forets_gpu_binding_20260911 import REAL_SINGULARITY
    code="""import ast,inspect,json,torch
from pathlib import Path
assert not torch.cuda.is_available()
for i in (0,1):
 tree=ast.parse(Path(f'/r14/programs/{i}.py').read_text())
 imports=ast.Module(body=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))],type_ignores=[])
 exec(compile(imports,'imports-only','exec'),{})
assert 'verbose' in inspect.signature(torch.optim.lr_scheduler.ReduceLROnPlateau).parameters
print(json.dumps({'imports_only':True,'torch':torch.__version__,'cuda_available':False}))
"""
    env={k:v for k,v in os.environ.items() if not k.startswith(('SINGULARITY','APPTAINER','CUDA','SLURM'))}
    cmd=[REAL_SINGULARITY,'exec','--cleanenv','--containall','--no-home','--no-mount','hostfs,bind-paths','--bind',str(R)+':/r14:ro',str(m.TASK_IMAGE),'python','-c',code]
    result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120)
    if result.returncode:raise ValueError('new source CPU dependency qualification failed')
    rows=[json.loads(v) for v in result.stdout.splitlines() if v.startswith('{')]
    if len(rows)!=1 or not rows[0]['imports_only'] or rows[0]['cuda_available']:raise ValueError('CPU dependency receipt')
    subprocess.run([str(c.n.PY),'-B','-m','unittest','test_neural_extension'],cwd=R,check=True)
    write(R/'extension-preflight.json',dict(plan_sha256=sha(R/'plan.json'),dependency=rows[0],source_pins=PINS,executions=0))
    print(json.dumps(dict(status='EXTENSION_PREPARED',plan_sha256=sha(R/'plan.json'),new_programs=2,planned=12,cap_gpu_hours=1.5)))


def worker(index):
    configure().runtime()
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    from bounded_readiness import wait_for_ready
    JupyterKernelClient.wait_for_ready=lambda self,timeout_seconds=None:wait_for_ready(self,120 if timeout_seconds is None else timeout_seconds)
    return c.n.worker(index)


def main():
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','controller','worker','readout','audit']);ap.add_argument('--commit');ap.add_argument('--index',type=int);ap.add_argument('--plan-sha');a=ap.parse_args()
    if a.mode=='prepare':return prepare(a.commit)
    configure()
    if a.mode=='worker':return worker(a.index)
    if a.mode in ('submit','controller'):
        c.r.check_inputs()
        if read(R/'extension-preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('extension preflight')
        return getattr(c.n,a.mode)()
    if a.mode=='readout':
        import neural_pool_readout as report
        report.R=R;report.REFERENCE_ARM='pipeline';return report.main()
    if not a.plan_sha:raise ValueError('independent plan pin')
    return c.audit(a.plan_sha)


if __name__=='__main__':sys.exit(main())
