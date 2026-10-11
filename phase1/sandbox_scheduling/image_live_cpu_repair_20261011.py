"""Independent v2 effect batch after v1 stopped before any search began.

Only fixes physical-core partitioning. Same32 configs/seeds/ABBA/scoring and
2400-second pool slots. Previous failure2634 GPU seconds remains separately.
Combined allocation cap2634+9720*6=60954 GPU seconds, below original61200.
"""
import argparse,json,os,re,secrets,shutil,subprocess,sys
from pathlib import Path
import image_live_2plus4_20261011 as trial
from lifecycle_pilot import read,write,sha
from image_cpu_partition_20261011 import partition

OLD=trial.R;OLD_PIN='b44f6002b5da35d953a0ae1ead7b88d7776428cf7e775a26475fcce545837e78'
R=trial.B/'scheduling-image-live-2plus4-20261011-v2';CAP=9720
trial.R=R;trial.CAP=CAP;trial.NAME=Path(__file__).name
host=trial.host

def worker(index):
    from live_identity import cpu_topology,cores
    topology=cpu_topology();slots=partition(topology)
    chosen=slots[trial.schedule()[index]['slot']%2]
    os.sched_setaffinity(0,chosen)
    after=cpu_topology();assert len(cores(after))==2 and set(os.sched_getaffinity(0))==set(chosen)
    ep=R/f'episode-{index}'
    write(ep/'cpu-partition.json',dict(parent_topology=topology,worker_topology=after,chosen=chosen,slot=index%2))
    # Initialize the CUDA driver AFTER CPU binding so its child threads inherit it.
    from resource_gpu_identity import gpu_uuids
    os.environ['CUDA_VISIBLE_DEVICES']=gpu_uuids(1)[0]
    return host().worker(index)

def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and sha(OLD/'plan.json')==OLD_PIN
    account=read(OLD/'accounting-v1.json');assert account['job']=='17587' and account['gpu_seconds']==2634
    assert read(OLD/'closed.json')['complete']==0 and not any(OLD.glob('episode-*/deadline.json'))
    p=read(OLD/'plan.json');assert all(sha(OLD/n)==h for n,h in p['files'].items())
    R.mkdir(mode=0o700)
    for n in p['files']:
        if n.startswith('configs/'):continue
        dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/n,dst)
    # The immutable old public-training development views are reused read-only.
    (R/'dev-views').symlink_to(OLD/'dev-views',target_is_directory=True)
    for b in range(4):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    (R/'configs').mkdir()
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(OLD),str(R)))
    for row in trial.schedule():
        ep=R/f"episode-{row['index']}";(ep/'work/input_cache').mkdir(parents=True)
        cfg=read(OLD/f"configs/{row['index']}.json")
        # Infrastructure paths only. Task inputs retain their original exact path.
        original=json.dumps(cfg,sort_keys=True)
        cfg=json.loads(original.replace(str(OLD),str(R)))
        for name in ('public_dir','data_dir','private_dir'):cfg['task'][name]=read(OLD/f"configs/{row['index']}.json")['task'][name]
        cfg['task']['search_only_dev_scorer_sha256']=sha(scorer)
        write(R/f"configs/{row['index']}.json",cfg)
    shim=R/'bin/singularity';shim.write_text(f'#!{trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n');shim.chmod(0o700)
    for n in (Path(__file__).name,'image_cpu_partition_20261011.py','test_image_cpu_partition_20261011.py'):
        shutil.copyfile(Path(__file__).with_name(n),R/n)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch';s=sb.read_text().replace(str(OLD),str(R)).replace('02:50:00','02:42:00').replace('10110s','9660s').replace('image_live_2plus4_20261011.py controller',Path(__file__).name+' controller');sb.write_text(s)
    subprocess.run(['bash','-n',str(sb)],check=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],allocation_seconds=CAP,gpu_hours_cap=CAP*6/3600,
        prior_failure=dict(job='17587',plan_sha256=OLD_PIN,gpu_seconds=2634,started_searches=0),
        combined_gpu_seconds_cap=2634+CAP*6,entry_repair='Partition four physical cores, not SMT thread count; one thread per physical core, two cores per run; CUDA init after binding.',
        reused_data_plan_sha256=OLD_PIN)
    p['files']={n:sha(R/n) for n in p['files']}
    for n in (Path(__file__).name,'image_cpu_partition_20261011.py','test_image_cpu_partition_20261011.py'):p['files'][n]=sha(R/n)
    write(R/'plan.json',p)
    assert p['combined_gpu_seconds_cap']<=17*3600
    trial.cpu()
    for a,b in [(i,i+8) for i in range(8)]+[(i,i+8) for i in range(16,24)]:
        assert trial.t.scientific(read(R/f'configs/{a}.json'))==trial.t.scientific(read(R/f'configs/{b}.json'))
    subprocess.run([str(trial.PY),'-B','-m','unittest','test_image_cpu_partition_20261011','test_image_live_20261011','-v'],cwd=R,check=True)
    write(R/'entry-repair-preflight.json',dict(commit=commit,plan_sha256=sha(R/'plan.json'),configs=32,pairs=16,
        physical_partition_tests=5,original_tests=9,old_failure_retained=True,combined_gpu_hours_cap=p['combined_gpu_seconds_cap']/3600))
    print(json.dumps(read(R/'entry-repair-preflight.json')))

def submit():
    p=trial.check();assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    assert all(sha(R/n)==h for n,h in p['input_files'].items())
    # A fresh bounded CPU-only check, not a GPU/model acceptance run.
    m=host();assert sha(m.TASK_IMAGE)==p['task_image_sha256'] and sha(m.VLLM)==p['service_image_sha256']
    assert all(sha(n)==h for n,h in p['model_files'].items())
    env=m.infra().clean_env();jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True).split()
    assert not set(jobs)-{'12535'}
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=CAP*6/3600,combined_gpu_hours_cap=p['combined_gpu_seconds_cap']/3600))
    out=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(submitted=True,job=job,gpu_hours_cap=CAP*6/3600,combined_gpu_hours_cap=p['combined_gpu_seconds_cap']/3600)))

if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','cpu','submit','controller','service','lane','worker']);p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--lane',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='submit':submit()
    elif a.mode=='worker':worker(a.index)
    elif a.mode=='service':trial.service(a.block)
    elif a.mode=='lane':trial.lane(a.block,a.lane)
    else:getattr(trial,a.mode)()
