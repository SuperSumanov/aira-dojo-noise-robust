"""New bounded request-timeout effect screen, not a rescue of job17592.

Six GPUs, 16 native900s searches; local generation timeout240 vs600 only.
Execution sharing remains2 in both arms. Two1500s pools include independent
service startup, idle and cleanup. One pool pair cannot establish a method.
"""
import argparse,json,os,re,secrets,shutil,subprocess
from pathlib import Path
import image_live_cpu_repair_20261011 as c
from lifecycle_pilot import read,write,sha

OLD=c.trial.B/'scheduling-image-live-2plus4-20261011-v3'
OLD_PIN='95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66'
R=c.trial.B/'scheduling-image-generation-deadline-20261011-v1'
CAP=3120; RUN=900; SLOT=1500
ARMS=('deadline600','deadline240')


def schedule():
    return [dict(index=8*b+2*lane+k,block=b,lane=lane,slot=2*lane+k,repeat=0,
        arm=arm,task=task,seed=212001+2*lane+k)
        for b,arm in enumerate(ARMS) for lane in range(4) for k,task in enumerate(c.trial.TASKS)]


def scientific_without_timeout(cfg):
    value=c.trial.t.scientific(cfg)
    for op in value['solver']['operators'].values():
        op['llm']['generation_kwargs'].pop('bounded_request_timeout_seconds')
    return value


def configure():
    c.R=R;c.CAP=CAP;c.host=c.trial.host
    c.trial.R=R;c.trial.CAP=CAP;c.trial.RUN_SECONDS=RUN;c.trial.SLOT_SECONDS=SLOT
    c.trial.NAME=Path(__file__).name;c.trial.schedule=schedule


def lane(block,index):
    c.trial.lane(block,index)
    for row in schedule():
        if (row['block'],row['lane'])!=(block,index):continue
        ep=R/f"episode-{row['index']}";result=read(ep/'closed.json')
        events=[json.loads(line) for line in (ep/'events.jsonl').read_text().splitlines()] if (ep/'events.jsonl').exists() else []
        if result['returncode']!=0 and not any(e['event']=='generation_started' for e in events):
            raise RuntimeError('pre-generation infrastructure failure; stop remaining pool')


def patch_driver(text):
    change=c.trial.change
    text=change(text,"TIME_LIMIT='25 minutes',TIME_LIMIT_SECS='1500'","TIME_LIMIT='15 minutes',TIME_LIMIT_SECS='900'")
    text=change(text,"'timeout=1590'","'timeout=990'")
    text=change(text,'for block in range(4):','for block in range(2):')
    text=change(text,'dict(planned=32,attempted_blocks=attempted','dict(planned=16,attempted_blocks=attempted')
    # CPU receipt must describe the actual new matrix, not the old32 rows.
    text=change(text,'dict(configs=32,paired_equal=16,no_kernel=True','dict(configs=16,paired_equal=8,no_kernel=True')
    return text


def patch_timeout_guard(text):
    text=c.trial.change(text,'0 < timeout_seconds <= 300','0 < timeout_seconds <= 600')
    return c.trial.change(text,'in (0, 300] seconds','in (0, 600] seconds')


def preflight():
    p=c.trial.check();c.trial.cpu()
    for a,b in zip(schedule()[:8],schedule()[8:]):
        ac,bc=read(R/f"configs/{a['index']}.json"),read(R/f"configs/{b['index']}.json")
        assert (a['task'],a['seed'],a['lane'])==(b['task'],b['seed'],b['lane'])
        assert scientific_without_timeout(ac)==scientific_without_timeout(bc)
        for row,cfg in ((a,ac),(b,bc)):
            assert cfg['solver']['time_limit_secs']==RUN and cfg['interpreter']['timeout']==300
            assert all(op['llm']['generation_kwargs']['bounded_request_timeout_seconds']==int(row['arm'][8:])
                for op in cfg['solver']['operators'].values())
    write(R/'preflight.json',dict(configs=16,matched_pairs=8,source_commit=p['source_commit'],
        plan_sha256=sha(R/'plan.json'),execution_permits_both=2,run_seconds=RUN,no_gpu_used=True))
    print(json.dumps(read(R/'preflight.json')))


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and sha(OLD/'plan.json')==OLD_PIN
    assert read(OLD/'completion-closed.json')['exploratory_go'] is False
    p=read(OLD/'plan.json');assert all(sha(OLD/n)==h for n,h in p['files'].items())
    R.mkdir(mode=0o700)
    for name in p['files']:
        if name.startswith('configs/'):continue
        target=R/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/name,target)
    (R/'dev-views').symlink_to((OLD/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(2):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(OLD),str(R)))
    for row in schedule():
        index=row['index'];ep=R/f'episode-{index}';(ep/'work/input_cache').mkdir(parents=True)
        cfg=read(OLD/f'configs/{index%8}.json')
        cfg=json.loads(json.dumps(cfg).replace(str(OLD),str(R)))
        cfg['id']='image-generation-deadline-'+str(index)
        cfg['metadata'].update(seed=row['seed'],script_id='image-generation-deadline-20261011')
        cfg['solver'].update(checkpoint_path=str(ep/'checkpoint'),time_limit_secs=RUN)
        cfg['logger']['output_dir']=str(ep/'native-log')
        cfg['task'].update(results_output_dir=str(ep/'native-task-results'),search_only_dev_scorer_sha256=sha(scorer))
        cfg['interpreter']['working_dir']=str(ep/'work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        for op in cfg['solver']['operators'].values():
            op['llm']['generation_kwargs'].update(seed=row['seed'],bounded_request_timeout_seconds=int(row['arm'][8:]))
        write(R/f'configs/{index}.json',cfg)
    driver=R/'image_live_2plus4_20261011.py';driver.write_text(patch_driver(driver.read_text()))
    transport=R/'source/src/dojo/core/solvers/llm_helpers/backends/lite_llm.py'
    transport.write_text(patch_timeout_guard(transport.read_text()))
    names=(Path(__file__).name,'image_deadline_readout_20261011.py')
    for name in names:shutil.copyfile(Path(__file__).with_name(name),R/name)
    shim=R/'bin/singularity'
    shim.write_text(f'#!{c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n');shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch';text=sb.read_text().replace(str(OLD),str(R))
    text=c.trial.change(text,'02:30:00','00:52:00');text=c.trial.change(text,'8940s','3060s')
    text=c.trial.change(text,'image_live_identity_repair_20261011.py controller',Path(__file__).name+' controller')
    text=c.trial.change(text,'r14-image-quality','r14-request-quality');sb.write_text(text)
    subprocess.run(['bash','-n',str(sb)],check=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],schedule=schedule(),planned=16,
        allocation_seconds=CAP,gpu_hours_cap=CAP*6/3600,run_seconds=RUN,slot_seconds=SLOT,
        source_donor_plan_sha256=OLD_PIN,request_seconds={'deadline240':240,'deadline600':600},
        combined_gpu_seconds_cap=CAP*6,prior_failures=[],prior_failure=None,
        execution_permits=2,independent_pool_pairs=1,
        primary='All16 assigned; valid native-selected development endpoints and task-stratified paired scores at900s, no missing-score imputation.',
        secondary='First generation survival, valid timely candidate returns, pool task best, all-cost accounting.',
        single_change='Local generation bounded request timeout240 vs600; execution sharing2,900s total run,300s candidate and1500s pool budgets held fixed.',
        advance='Screen only: all16 attempted with cleanup, fewer first-generation failures and more valid endpoints overall without per-task endpoint decrease. No auto expansion; one pool pair is not confirmation.',
        limitation='New shorter common900s search setting; no comparison with old1500s scores. One fixed-order pool pair, reused development tasks, no population claim. No SchedMate novelty.',
        stop='Stop remaining pool on isolation, cleanup or pre-generation infrastructure failure. Keep all16 assigned; no replacement or automatic rerun.',
        entry_repair=None,pool_padding_change=None)
    p['files']={n:sha(R/n) for n in p['files'] if not n.startswith('configs/')}
    p['files'].update({f'configs/{i}.json':sha(R/f'configs/{i}.json') for i in range(16)})
    for name in names:p['files'][name]=sha(R/name)
    write(R/'plan.json',p)
    # Load the patched common driver only in a fresh interpreter.
    subprocess.run([str(c.trial.PY),'-B',str(R/Path(__file__).name),'preflight'],cwd=R,check=True)


configure()
host=c.trial.host;worker=c.worker;submit=c.submit

if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','preflight','submit','controller','service','lane','worker'])
    p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--lane',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':submit()
    elif a.mode=='worker':worker(a.index)
    elif a.mode=='service':c.trial.service(a.block)
    elif a.mode=='lane':lane(a.block,a.lane)
    else:c.trial.controller()
