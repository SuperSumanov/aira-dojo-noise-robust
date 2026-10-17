"""Public-source-page headroom assay. Classical controls, NOT a new method.

New protocol: all four programs may use CPU or CUDA in the same resource envelope.
Old CUDA-required R14 gates and data are unchanged. No generation or old-batch retry.
"""
import argparse, ast, csv, hashlib, json, os, re, shutil, socket, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone
import rng_selection_pilot_20261018 as reuse
import clock_contention_20261016 as base
from candidate_family_screen_20261018 import SECRET

B=Path('/research/d7/spc/yzyang4')
R=B/'page-headroom-20261018-v1'
PUBLIC=B/'scheduling-image-live-2plus4-20261011-v1/dev-views/denoising-dirty-documents/public'
TASK='denoising-dirty-documents'
PY=B/'venvs/aira/bin/python'
NAME=Path(__file__).name
CAP=7200
LATEST=datetime(2026,10,17,23,15,tzinfo=timezone.utc).timestamp()
sha,read,write=base.sha,base.read,base.write
BATCHES=('scheduling-pooling-20261016-v3','scheduling-colocation-20261016-v1','scheduling-selective-20261017-v1')

def schedule():
    orders=((0,1,2,3),(3,2,1,0),(1,0,3,2),(2,3,0,1))
    return [dict(index=b*4+j,block=b,fold=b//2,seed=5221+b%2,program=k,
                 mode=('cnn0','cnn1','patch','multiscale')[k],slot=0,task=TASK)
            for b in range(4) for j,k in enumerate(orders[b])]

def setup():
    m=base.setup();os.environ['LOGGING_DIR']=str(R)
    reuse.R=R;reuse.NAME=NAME;reuse.setup=setup;reuse.check=check
    return m

def choose():
    candidates=[]
    for batch in BATCHES:
        root=B/batch;assert (root/'closed.json').is_file()
        for row in read(root/'plan.json')['schedule']:
            if row['task']!=TASK:continue
            ep=root/f"episode-{row['index']}"
            for p in sorted(ep.glob('candidate-*.json')):
                if '.private.' in p.name:continue
                c=read(p)
                if not(c.get('valid') and c.get('exit_code')==0 and not c.get('timed_out') and c['elapsed_seconds']<=1020):continue
                scores=[(s,read(s)['receipt']) for s in sorted(ep.glob('scored-*.json'))
                        if read(s)['receipt']['submission_sha256']==c['aux']['submission_sha256']]
                assert scores and len({s['rmse'] for _,s in scores})==1
                code=read(p.with_name(p.stem+'.private.json'))['code']
                assert not SECRET.search(code)
                assert hashlib.sha256(code.encode()).hexdigest()==c['code_sha256']
                ast.parse(code)
                candidates.append(dict(batch=batch,episode=row['index'],candidate=int(p.stem.split('-')[1]),
                    score=scores[0][1]['rmse'],code_sha256=c['code_sha256'],code=code,
                    receipt_sha256=sha(p),source_config=str(root/f"configs/{row['index']}.json")))
    unique={}
    for c in sorted(candidates,key=lambda c:(c['score'],c['batch'],c['episode'],c['candidate'])):
        unique.setdefault(c['code_sha256'],c)
    assert len(unique)>=2
    return list(unique.values())[:2],len(unique)

def make_view(fold):
    from PIL import Image
    import numpy as np
    root=R/f'views/fold-{fold}';pub=root/'public';refs=root/'search-reference'
    for d in ('train','train_cleaned','test'):(pub/d).mkdir(parents=True)
    refs.mkdir(mode=0o700)
    names=sorted(p.name for p in (PUBLIC/'train_cleaned').glob('*.png'))
    hashes={n:hashlib.sha256(np.asarray(Image.open(PUBLIC/'train_cleaned'/n).convert('L'),dtype=np.uint8).tobytes()).hexdigest() for n in names}
    groups=sorted(set(hashes.values()),key=lambda h:hashlib.sha256(('page-headroom-v1:'+h).encode()).digest())
    assert len(names)==92 and len(groups)==36
    query_groups=set(groups[fold*12:(fold+1)*12])
    query=[n for n in names if hashes[n] in query_groups];train=[n for n in names if n not in query]
    assert not {hashes[n] for n in train}&{hashes[n] for n in query}
    dims={};source={}
    for n in names:
        for d in ('train','train_cleaned'):
            p=PUBLIC/d/n;source[str(p)]=sha(p)
            dest=(pub/d/n if n in train else pub/'test'/n if d=='train' else refs/n)
            shutil.copyfile(p,dest)
        with Image.open(PUBLIC/'train'/n) as im:dims[n]=im.size
    with (pub/'test.csv').open('x',newline='') as f,(pub/'sample_submission.csv').open('x',newline='') as g:
        a,b=csv.writer(f),csv.writer(g);a.writerow(['id']);b.writerow(['id','value'])
        for n in query:
            w,h=dims[n]
            for y in range(1,h+1):
                for x in range(1,w+1):
                    name=f'{int(Path(n).stem)}_{y}_{x}';a.writerow([name]);b.writerow([name,.5])
    (pub/'description.md').write_text('Paired grayscale document denoising. Train only on train and train_cleaned. '
        'Predict test images to /workspace/submission.csv with id,value; row/column are one-based. '
        'RMSE, values [0,1]. Same resource envelope permits CPU or CUDA algorithms. No external downloads. '
        'Finish within 300 seconds. This is a public-training-only exploratory source-page split, not official test.\n')
    manifest=dict(task=TASK,split_seed='page-headroom-v1',train_ids=train,query_ids=query,reserved_ids=[],
        source_files=source,public_files={str(p.relative_to(pub)):sha(p) for p in pub.rglob('*') if p.is_file()},
        search_reference_files={p.name:sha(p) for p in refs.iterdir()},
        query_dimensions={n:dims[n] for n in query},not_confirmation=True,not_official_test=True,
        reserved_content_not_copied=True,source_group_disjoint=True,train_groups=24,query_groups=12)
    write(root/'manifest.json',manifest)
    return dict(view=str(root),view_sha=sha(root/'manifest.json'),lower_is_better=True,metric_name='rmse')

def prepare(commit,node):
    assert re.fullmatch('[a-f0-9]{40}',commit) and node in ('gpu1','gpu3','gpu27','gpu28','gpu29')
    runtime=setup();chosen,n=choose()
    for c in chosen:
        seed_calls=[ast.unparse(x) for x in ast.walk(ast.parse(c['code'])) if isinstance(x,ast.Call)
            and isinstance(x.func,ast.Attribute) and x.func.attr in ('seed','manual_seed','manual_seed_all')]
        assert not seed_calls,'strongest source overrides seed; do not silently pick weaker source'
    assert not R.exists();R.mkdir(mode=0o700)
    for d in ('bin','programs','configs'):(R/d).mkdir()
    for name in (NAME,'page_pixel_baseline_20261018.py','candidate_family_screen_20261018.py',
                 'rng_selection_pilot_20261018.py','clock_contention_20261016.py','image_dev_data_20261011.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    specs=[make_view(f) for f in (0,1)]
    for f,spec in enumerate(specs):
        write(R/f'views/spec-{f}.json',{TASK:spec})
        (R/f'image_scorer_{f}.py').write_text('from pathlib import Path\nimport json\nfrom image_dev_data_20261011 import InvalidSubmissionError,score_at\n'
            f'BASE=Path({str(R)!r})\nSPEC=json.loads((BASE/"views/spec-{f}.json").read_text())\n'
            'def score(task,submission):return score_at(BASE,SPEC,task,submission)\n')
    from dojo.config_dataclasses.run import RunConfig
    from dojo.utils.code_parsing import extract_code
    sources=[]
    for k,c in enumerate(chosen):
        (R/f'programs/cnn-{k}.private.py').write_text(c['code'])
        seed_calls=[ast.unparse(x) for x in ast.walk(ast.parse(c['code'])) if isinstance(x,ast.Call)
            and isinstance(x.func,ast.Attribute) and x.func.attr in ('seed','manual_seed','manual_seed_all')]
        # Fail before any submission if these programs override the experimental RNG.
        assert not seed_calls,'selected strongest source overrides seed; do not silently pick weaker source'
        sources.append({a:v for a,v in c.items() if a!='code'})
    rows=schedule()
    for row in rows:
        i,k,f=row['index'],row['program'],row['fold'];ep=R/f'episode-{i}';(ep/'work/input_cache').mkdir(parents=True)
        donor=chosen[k if k<2 else 0];cfg=read(donor['source_config'])
        old=str(B/donor['batch']/f"episode-{donor['episode']}")
        cfg=json.loads(json.dumps(cfg).replace(old,str(ep)))
        view=Path(specs[f]['view']);scorer=R/f'image_scorer_{f}.py'
        cfg['id']=f'page-headroom-{i}'
        cfg['task'].update(data_dir=str(view/'public'),public_dir=str(view/'public'),private_dir=str(view/'private-unavailable'),
            cache_dir=str(R/'no-official-data'),search_only_dev_scorer_path=str(scorer),search_only_dev_scorer_sha256=sha(scorer))
        cfg['interpreter']['env'].update(PYTHONHASHSEED=str(row['seed']),PAGE_STUDY_SEED=str(row['seed']),PAGE_STUDY_MODEL=row['mode'])
        cfg['logger'].update(write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        write(R/f'configs/{i}.json',cfg)
        conf=RunConfig.load_from_json(R/f'configs/{i}.json');conf.validate()
        assert not Path(conf.task.private_dir).exists() and conf.interpreter.timeout==300
        code=chosen[k]['code'] if k<2 else (R/'page_pixel_baseline_20261018.py').read_text()
        action=base.executable(code,row['seed']);ast.parse(extract_code(action))
        (R/f'programs/action-{i}.private.py').write_text(action)
        row['executed_sha256']=hashlib.sha256(extract_code(action).encode()).hexdigest()
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import task_runtime\ntask_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    (R/'run.sbatch').write_text(f'''#!/bin/bash
#SBATCH --job-name=page-headroom
#SBATCH --partition=gpu_24h
#SBATCH --nodelist={node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --hint=nomultithread
#SBATCH --time=02:00:00
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec srun --exclusive --ntasks=1 --cpus-per-task=2 --gres=gpu:1 {PY} -B {R/NAME} run
''')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'plan.json',dict(source_commit=commit,schedule=rows,programs=sources,historical_distinct_sources=n,
        views=specs,gpus=1,node=node,allocation_seconds=CAP,execution_seconds=300,latest_start_utc=LATEST,
        runtime_plan_sha256=sha(base.D/'plan.json'),runtime_files=read(base.D/'plan.json')['files'],
        task_image=str(runtime.TASK_IMAGE),task_image_sha256=read(base.D/'plan.json')['task_image_sha256'],
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not p.relative_to(R).parts[0].startswith('episode-')},
        question='Is there candidate-family headroom above historical CNNs after excluding repeated clean pages?',
        primary='All16 valid and integrity-qualified; multiscale RMSE at least .001 lower than BOTH historical CNNs AND patch LightGBM in each of 2folds x2seeds. Otherwise no opportunity qualification.',
        selection='Two best distinct timely-valid original DEV sources across all three closed batches 18770/18807/18997. No source replacement.',
        fairness='All four algorithms receive the same public fold,300s,2physicalCPU and one same physical3090. CPU-only models explicitly allowed in THIS NEW protocol, never a silent R14 fallback.',
        limits=['Classical model/feature controls, not an invented method or automated generation gain.',
                'One task; public source groups re-used across folds, not independent tasks or a new protected cohort.',
                'Historical code selection used oldDEV; training starts from scratch. All historical/init cost is a shared sunk asset, not free E2E generation.',
                'Uniform per-rendering training sampling is identical in both pixel feature arms; no query labels in training.'],
        stop='Missing/invalid candidate, isolation/cleanup/infrastructure failure stops qualification; retain all16 assigned denominator. No automatic retries/replacements. Old batches unchanged.'))
    print(json.dumps(dict(prepared=True,root=str(R),plan_sha256=sha(R/'plan.json'),runs=16,gpu_hours_cap=2,
                         cnn_sources=sources,view_counts=[{k:read(Path(s['view'])/'manifest.json')[k] for k in ('train_groups','query_groups')} for s in specs])))

def check():
    p=read(R/'plan.json')
    for n,h in p['files'].items():assert sha(R/n)==h
    assert sha(base.D/'plan.json')==p['runtime_plan_sha256']
    return p

def preflight():
    p=check();runtime=setup()
    from unittest.mock import patch
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    import dojo.core.interpreters.jupyter.jupyter_interpreter as native
    native._gateway_port=lambda:51991
    for row in p['schedule']:
        c=RunConfig.load_from_json(R/f"configs/{row['index']}.json");c.validate()
        public=Path(p['views'][row['fold']]['view'])/'public'
        assert Path(c.task.data_dir)==public==Path(c.task.public_dir)
        assert not Path(c.task.private_dir).exists() and not c.logger.use_wandb and not c.logger.write_env_vars
        with patch('dojo.core.interpreters.jupyter.jupyter_interpreter.SingularityJupyterServer') as server:
            factory=build(c.interpreter,INTERPRETER_MAP,data_dir=c.task.data_dir)
            assert factory.instance.timeout==300 and factory.instance.port==51991
            assert server.call_args.kwargs['bind_inputs_dir']==public
            factory.close()
    from forets_gpu_binding_20260911 import REAL_SINGULARITY
    test='import json,torch,scipy,lightgbm,numpy;print(json.dumps(dict(torch=torch.__version__,scipy=scipy.__version__,lightgbm=lightgbm.__version__,numpy=numpy.__version__)))'
    deps=subprocess.run([REAL_SINGULARITY,'exec','--containall','--cleanenv',str(runtime.TASK_IMAGE),'python','-c',test],
                        text=True,capture_output=True,timeout=90)
    assert deps.returncode==0,'original task image CPU dependency check failed'
    versions=json.loads(deps.stdout.strip().splitlines()[-1])
    import numpy as np
    from scipy.ndimage import gaussian_filter,median_filter,minimum_filter,maximum_filter
    tree=ast.parse((R/'page_pixel_baseline_20261018.py').read_text())
    fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='features')
    ns=dict(np=np,gaussian_filter=gaussian_filter,median_filter=median_filter,minimum_filter=minimum_filter,maximum_filter=maximum_filter)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<feature-test>','exec'),ns)
    x=np.arange(30,dtype=np.float32).reshape(5,6)/30
    ns['mode']='patch';a=ns['features'](x)
    ns['mode']='multiscale';b=ns['features'](x)
    assert a.shape==(30,9) and b.shape==(30,21) and np.array_equal(a,b[:,:9])
    checks=dict(actual_factory_configs=16,public_only_bind=True,source_page_overlap=0,
        original_task_image_cpu_dependency_versions=versions,feature_columns=[9,21],same_patch_columns=True,
        n_tasks=1,n_source_folds=2,n_seeds=2,n_programs=4,gpu_hours_cap=2,
        planned_denominator=16,new_source_page_split=True,no_gpu_or_api_in_preflight=True,
        artifact_knob_check='Per-run config model/fold/seed, execution hash, CUDA-gradient receipt for CNN and zero for explicitly CPU references',
        score_and_cost='Original pristine RMSE code; all16 assigned retained; complete>=.001 in everyfold/seed vs all3 controls; full allocation cost',
        statistical_limit='Exploratory family headroom, not a significant cross-task or E2E result; prior code selection cost remains shared historical cost',
        memory='No reusable agent checkpoint or agent training; task predictions retained remotely, no protected data',
        matrix_source_sha256=sha(R/NAME),plan_sha256=sha(R/'plan.json'))
    write(R/'preflight.json',checks);print(json.dumps(checks))

def task_runtime():setup();return reuse.task_runtime()
def worker(i):setup();return reuse.worker(i)

def run():
    p=check();setup();start=time.monotonic();records=[];error=None
    if time.time()>LATEST:
        write(R/'window-refusal.json',dict(no_workers_started=True));return 2
    from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology
    from live_search_trial_20261009 import owned_cleanup,gpu_sample,process_gone
    assert socket.gethostname().split('.')[0]==p['node']
    cores={}
    for x in cpu_topology():cores.setdefault((x['socket'],x['core']),[]).append(x['logical_cpu'])
    cpus=sorted(min(v) for v in cores.values());assert len(cpus)==2
    own=gpu_uuids(1);assert not gpu_sample(own[0])['pids']
    write(R/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own,cpu_slots=[cpus],wall=time.time()))
    try:
        for row in p['schedule']:
            if time.monotonic()-start>CAP-430:raise TimeoutError('no complete next execution fits')
            i=row['index'];ep=R/f'episode-{i}';began=time.monotonic()
            with (ep/'worker.private.log').open('xb') as f:
                proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(i)],stdout=f,stderr=f,start_new_session=True)
                try:proc.wait(timeout=390)
                finally:owned_cleanup(proc,ep)
            ident=read(ep/'identity.json') if (ep/'identity.json').exists() else {}
            clean=bool(ident) and all(process_gone(ident.get(a),ident.get(b)) for a,b in (('pid','process_start_ticks'),('container_pid','container_process_start_ticks')))
            fin=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
            records.append(dict(index=i,returncode=proc.poll(),cleanup=clean,elapsed_seconds=time.monotonic()-began,valid=fin.get('valid')))
            assert proc.returncode==0 and clean and fin.get('valid') and not gpu_sample(own[0])['pids']
            tr=read(ep/'training.safe.json')
            assert (tr['cuda_gradient_steps']>0) if row['program']<2 else tr['cuda_gradient_steps']==0
    except BaseException as exc:error=dict(type=type(exc).__name__,completed=len(records))
    finally:write(R/'closed.json',dict(planned=16,records=records,error=error,elapsed_seconds=time.monotonic()-start,cleanup_verified=not gpu_sample(own[0])['pids']))
    return int(error is not None)

def submit():
    p=check();assert time.time()<LATEST-60 and not (R/'submit-intent.json').exists()
    assert read(R/'preflight.json')['plan_sha256']==sha(R/'plan.json')
    assert Path(p['task_image']).stat().st_size==19717783552
    for name,h in p['runtime_files'].items():assert sha(base.D/name)==h
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),wall=time.time()))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    v=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.private.out'),
        '--error='+str(R/'allocation-%j.private.err'),str(R/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=v.stdout.strip().split(';')[0]
    if v.returncode or not job.isdigit():raise RuntimeError('submission ambiguous; inspect, never blindly retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')));print(json.dumps(dict(submitted=True,job=job)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','preflight','submit','run','worker'));p.add_argument('--commit');p.add_argument('--node',default='gpu3');p.add_argument('--index',type=int)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.commit,a.node)
    elif a.action=='preflight':preflight()
    elif a.action=='submit':submit()
    elif a.action=='worker':sys.exit(worker(a.index))
    else:sys.exit(run())
