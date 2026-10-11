"""Fresh ABBA quality replication of17656; 32 runs, 6GPU x6120s maximum.

Only240/600s request deadlines differ. Four900s searches/task/pool form
the fixed-budget task portfolio. Prior outcomes are never merged into this batch.
"""
import argparse,json,os,re,secrets,shutil,subprocess
from pathlib import Path
import image_generation_deadline_20261011 as donor
from lifecycle_pilot import read,write,sha

c=donor.c
OLD=c.trial.B/'scheduling-image-generation-deadline-20261011-v1'
OLD_PIN='d153e408fb88e7ac120fceadbab79528275943e356a639871abb7e9dcc5f86b7'
R=c.trial.B/'scheduling-image-deadline-replication-20261012-v1'
CAP=6120;RUN=900;SLOT=1500
ORDER=('deadline240','deadline600','deadline600','deadline240')


def schedule():
    return [dict(index=8*b+2*lane+k,block=b,lane=lane,slot=2*lane+k,repeat=b//2,
        arm=arm,task=task,seed=212101+100*(b//2)+2*lane+k)
        for b,arm in enumerate(ORDER) for lane in range(4) for k,task in enumerate(c.trial.TASKS)]


def configure():
    c.R=R;c.CAP=CAP;c.host=c.trial.host
    c.trial.R=R;c.trial.CAP=CAP;c.trial.RUN_SECONDS=RUN;c.trial.SLOT_SECONDS=SLOT
    c.trial.NAME=Path(__file__).name;c.trial.schedule=schedule


def resolve_lane(devices,gpu):
    assert len(devices)==len(set(devices))==4 and gpu in devices
    return devices.index(gpu)


def lane(block,requested):
    from resource_gpu_identity import gpu_uuids
    index=requested
    if block:
        devices=[read(R/f'block-0/lane-{i}-native.json')['gpu_uuid'] for i in range(4)]
        index=resolve_lane(devices,gpu_uuids(1)[0])
    write(R/f'block-{block}/lane-request-{requested}.json',dict(requested=requested,logical=index))
    c.trial.lane(block,index)
    for row in schedule():
        if (row['block'],row['lane'])!=(block,index):continue
        ep=R/f"episode-{row['index']}";result=read(ep/'closed.json')
        events=[json.loads(x) for x in (ep/'events.jsonl').read_text().splitlines()] if (ep/'events.jsonl').exists() else []
        if result['returncode']!=0 and not any(e['event']=='generation_started' for e in events):
            raise RuntimeError('pre-generation infrastructure failure')


def patch_driver(text):
    change=c.trial.change
    text=change(text,'for block in range(2):','for block in range(4):')
    text=change(text,'dict(planned=16,attempted_blocks=attempted','dict(planned=32,attempted_blocks=attempted')
    text=change(text,'dict(configs=16,paired_equal=8,no_kernel=True','dict(configs=32,paired_equal=16,no_kernel=True')
    # The existing verified pool is reused; require its service pair to stay fixed.
    anchor="                    write(bd/'service-ready.json',dict(startup_seconds=time.monotonic()-begin))"
    return change(text,anchor,"""                    if block:
                        assert set(read(bd/'service-native.json')['gpu_uuids'])==set(read(R/'block-0/service-native.json')['gpu_uuids']), 'service GPU drift'
"""+anchor)


def preflight():
    p=c.trial.check();c.trial.cpu()
    rows=schedule()
    for a in [r for r in rows if r['arm']=='deadline240']:
        b=next(r for r in rows if r['arm']=='deadline600' and r['seed']==a['seed'])
        ac,bc=(read(R/f"configs/{r['index']}.json") for r in (a,b))
        assert (a['task'],a['lane'],a['repeat'])==(b['task'],b['lane'],b['repeat'])
        assert donor.scientific_without_timeout(ac)==donor.scientific_without_timeout(bc)
        for row,cfg in ((a,ac),(b,bc)):
            assert cfg['solver']['time_limit_secs']==RUN and cfg['interpreter']['timeout']==300
            assert all(op['llm']['generation_kwargs']['bounded_request_timeout_seconds']==int(row['arm'][8:]) for op in cfg['solver']['operators'].values())
    write(R/'preflight.json',dict(configs=32,matched_pairs=16,source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),no_gpu=True,independent_pool_pairs=2))
    print(json.dumps(read(R/'preflight.json')))


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and sha(OLD/'plan.json')==OLD_PIN
    assert read(OLD/'completion-closed.json')['screen_positive'] is True
    p=read(OLD/'plan.json');assert all(sha(OLD/n)==h for n,h in p['files'].items())
    R.mkdir(mode=0o700)
    for name in p['files']:
        if name.startswith('configs/'):continue
        target=R/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/name,target)
    (R/'dev-views').symlink_to((OLD/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(4):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(OLD),str(R)))
    for row in schedule():
        i=row['index'];ep=R/f'episode-{i}';(ep/'work/input_cache').mkdir(parents=True)
        cfg=read(OLD/f'configs/{i%8}.json');cfg=json.loads(json.dumps(cfg).replace(str(OLD),str(R)))
        cfg['id']='image-deadline-replication-'+str(i)
        cfg['metadata'].update(seed=row['seed'],script_id='image-deadline-replication-20261012')
        cfg['solver'].update(checkpoint_path=str(ep/'checkpoint'),time_limit_secs=RUN)
        cfg['logger']['output_dir']=str(ep/'native-log');cfg['task'].update(results_output_dir=str(ep/'native-task-results'),search_only_dev_scorer_sha256=sha(scorer))
        cfg['interpreter']['working_dir']=str(ep/'work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        for op in cfg['solver']['operators'].values():op['llm']['generation_kwargs'].update(seed=row['seed'],bounded_request_timeout_seconds=int(row['arm'][8:]))
        write(R/f'configs/{i}.json',cfg)
    driver=R/'image_live_2plus4_20261011.py';driver.write_text(patch_driver(driver.read_text()))
    names=(Path(__file__).name,'image_deadline_replication_readout_20261012.py','image_deadline_replication_finish_20261012.py','image_deadline_replication_status_20261012.py')
    for name in names:shutil.copyfile(Path(__file__).with_name(name),R/name)
    shim=R/'bin/singularity';shim.write_text(f'#!{c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n');shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch';s=sb.read_text().replace(str(OLD),str(R));s=c.trial.change(s,'00:52:00','01:42:00');s=c.trial.change(s,'3060s','6060s')
    s=c.trial.change(s,'image_generation_deadline_20261011.py controller',Path(__file__).name+' controller');sb.write_text(s)
    subprocess.run(['bash','-n',str(sb)],check=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],source_donor_plan_sha256=OLD_PIN,schedule=schedule(),planned=32,allocation_seconds=CAP,gpu_hours_cap=CAP*6/3600,combined_gpu_seconds_cap=CAP*6,independent_pool_pairs=2,
        primary='Per-task best native-selected valid endpoint among the four preassigned searches in each pool; both repeats and both tasks required. Missing remains null, no score imputation.',
        secondary='All32 run endpoints, complete-pair score deltas with missingness, valid completion coverage, generation survival, candidate feedback and all-cost ledger.',
        practical_margin={'aerial-cactus-identification':0.001,'denoising-dirty-documents':0.001},
        advance='Bounded replication signal only: four finite pool-task quality contrasts nonnegative, same task improves by>=0.001 in both repeats, per-pool/task endpoint coverage not lower, all32 started and all structure/identity/score checks pass. No automatic expansion.',
        limitation='Two independent seed sets, ABBA temporal order; reused development tasks, not heldout test or statistically confirmed general method. Pool-best is prespecified here, not retrofitted to17656.240s is our diagnostic control, not an upstream default.',
        device_mapping='Logical lane maps to block0 physical GPU; service GPU pair fixed; fail closed on any unknown device.',
        stop='Isolation/cleanup/pre-generation infrastructure failures stop remaining pools. Preserve32 assigned. No replacement, retuning or automatic retry.')
    p['files']={n:sha(R/n) for n in p['files'] if not n.startswith('configs/')}
    p['files'].update({f'configs/{i}.json':sha(R/f'configs/{i}.json') for i in range(32)})
    for name in names:p['files'][name]=sha(R/name)
    write(R/'plan.json',p)
    subprocess.run([str(c.trial.PY),'-B',str(R/Path(__file__).name),'preflight'],cwd=R,check=True)


configure();host=c.trial.host;worker=c.worker;submit=c.submit
if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','preflight','submit','controller','service','lane','worker']);p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--lane',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':submit()
    elif a.mode=='worker':worker(a.index)
    elif a.mode=='service':c.trial.service(a.block)
    elif a.mode=='lane':lane(a.block,a.lane)
    else:c.trial.controller()
