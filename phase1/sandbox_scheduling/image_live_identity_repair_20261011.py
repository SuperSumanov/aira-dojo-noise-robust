"""Independent v3 same-search-budget effect trial after two entry-only failures.

Keeps32 seeds/configs and1500s search budgets. Four pool slots2200s instead of
2400s remove common reserved idle padding. Six GPUs maximum9000s. Previous
conservative6216GPU seconds plus54000cap=60216GPU seconds, below17GPUh.
"""
import argparse,json,os,re,secrets,shutil,subprocess,sys
from pathlib import Path
import image_live_cpu_repair_20261011 as c
from lifecycle_pilot import read,write,sha
from image_cuda_contract_20261011 import patch_identity,patch_resolver

OLD=c.R;OLD_PIN='df7b44e3a89f5c6fd110424aeffd5ea7ad569cafa8a139ea667c1083614ab6e8'
R=c.trial.B/'scheduling-image-live-2plus4-20261011-v3';CAP=9000
c.R=R;c.CAP=CAP;c.trial.R=R;c.trial.CAP=CAP;c.trial.SLOT_SECONDS=2200;c.trial.NAME=Path(__file__).name
host=c.host;worker=c.worker;submit=c.submit

def lane(block,index):
    c.trial.lane(block,index)
    for row in c.trial.schedule():
        if row['block']!=block or row['lane']!=index:continue
        ep=R/f"episode-{row['index']}";result=read(ep/'closed.json')
        events=[json.loads(x) for x in (ep/'events.jsonl').read_text().splitlines()] if (ep/'events.jsonl').exists() else []
        if result['returncode']!=0 and not any(x['event']=='generation_started' for x in events):
            raise RuntimeError('pre-generation infrastructure failure; no later pools')

def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and sha(OLD/'plan.json')==OLD_PIN
    assert read(OLD/'launch.json')['job']=='17590' and read(OLD/'completion-incomplete.json')['reason']=='missing controller closure'
    assert not any(OLD.glob('episode-*/candidate-*.json'))
    p=read(OLD/'plan.json');assert all(sha(OLD/n)==h for n,h in p['files'].items())
    R.mkdir(mode=0o700)
    for n in p['files']:
        if n.startswith('configs/'):continue
        dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/n,dst)
    (R/'dev-views').symlink_to((OLD/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for block in range(4):(R/f'block-{block}/service-cache/tmp').mkdir(parents=True)
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(OLD),str(R)))
    for row in c.trial.schedule():
        ep=R/f"episode-{row['index']}";(ep/'work/input_cache').mkdir(parents=True)
        cfg=read(OLD/f"configs/{row['index']}.json")
        cfg=json.loads(json.dumps(cfg).replace(str(OLD),str(R)))
        cfg['task']['search_only_dev_scorer_sha256']=sha(scorer)
        write(R/f"configs/{row['index']}.json",cfg)
    files=(Path(__file__).name,'image_cuda_contract_20261011.py','test_image_cuda_contract_20261011.py')
    for n in files:shutil.copyfile(Path(__file__).with_name(n),R/n)
    identity=R/'forets_native_cuda_identity_20260911.py';identity.write_text(patch_identity(identity.read_text()))
    resolver=R/'forets_native_gpu_binding_20260911.py';resolver.write_text(patch_resolver(resolver.read_text()))
    shim=R/'bin/singularity';shim.write_text(f'#!{c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n');shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch';sb.write_text(sb.read_text().replace(str(OLD),str(R)).replace('02:42:00','02:30:00').replace('9660s','8940s').replace('image_live_cpu_repair_20261011.py controller',Path(__file__).name+' controller'))
    subprocess.run(['bash','-n',str(sb)],check=True)
    reader=R/'image_live_readout_20261011.py'
    reader.write_text(c.trial.change(reader.read_text(),"budget.get('reserved_seconds')==2400","budget.get('reserved_seconds')==p['slot_seconds']"))
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],allocation_seconds=CAP,gpu_hours_cap=CAP*6/3600,slot_seconds=2200,
        prior_failures=[dict(job='17587',gpu_seconds=2634),dict(job='17590',scheduler_gpu_seconds=3576,conservative_gpu_seconds=3582)],
        combined_gpu_seconds_cap=6216+CAP*6,prior_failure=None,reused_data_plan_sha256=OLD_PIN,
        entry_repair='Accept verified single UUID as well as legacy0; keep device_count/driverPCI/device-node/expectedUUID/namespace checks. Physical CPU split fromv2. Abort remaining pools on pre-generation infrastructure failure.',
        pool_padding_change='Same1500s search and300s candidate budgets, same32seeds. Common reserved pool padding2400 to2200s for botharms to retain total17GPUh after entry failures.')
    p['files']={n:sha(R/n) for n in p['files']}
    for n in files:p['files'][n]=sha(R/n)
    write(R/'plan.json',p);assert p['combined_gpu_seconds_cap']<=17*3600
    c.trial.cpu()
    for a,b in [(i,i+8) for i in range(8)]+[(i,i+8) for i in range(16,24)]:
        assert c.trial.t.scientific(read(R/f'configs/{a}.json'))==c.trial.t.scientific(read(R/f'configs/{b}.json'))
    subprocess.run([str(c.trial.PY),'-B','-m','unittest','test_image_cpu_partition_20261011','test_image_cuda_contract_20261011','test_image_live_20261011','-v'],cwd=R,check=True)
    write(R/'entry-repair-preflight.json',dict(commit=commit,plan_sha256=sha(R/'plan.json'),configs=32,pairs=16,tests=24,
        same_search_budget=True,prior_failures_retained=True,combined_gpu_hours_cap=p['combined_gpu_seconds_cap']/3600))
    print(json.dumps(read(R/'entry-repair-preflight.json')))

if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','cpu','submit','controller','service','lane','worker']);p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--lane',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='submit':submit()
    elif a.mode=='worker':worker(a.index)
    elif a.mode=='service':c.trial.service(a.block)
    elif a.mode=='lane':lane(a.block,a.lane)
    else:getattr(c.trial,a.mode)()
