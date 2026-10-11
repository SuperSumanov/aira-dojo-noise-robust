"""New bounded integration batch; normalize only an already verified CUDA UUID.

V1 remains closed1attempt/0accepted/6GPUseconds. No changes to senior source,
candidate, image, timeout or matrix. Exception frames contain no values/code.
"""
import inspect,json,os,shutil,subprocess,sys,traceback
from pathlib import Path
import factory_integration_20261011 as old

ROOT=old.BASE/'resource-factory-integration-20261011-v2'
DONOR=old.ROOT
PIN='e25b471a56c77cd1b17afc7d004bd3bfaa300a3dbe4beb7d55e6b2274247c33a'
NAME=Path(__file__).name

def fixed_run(source):
    a='configure();device=gpu_uuids(1)[0];top=cpu_topology();assert len(cores(top))==4'
    b="configure();device=gpu_uuids(1)[0];os.environ['CUDA_VISIBLE_DEVICES']=device;top=cpu_topology();assert len(cores(top))==4"
    assert source.count(a)==1;source=source.replace(a,b)
    a="            except Exception as exc:row['error_type']=type(exc).__name__"
    b="""            except Exception as exc:
                row['error_type']=type(exc).__name__
                row['error_frames']=[dict(file=Path(x.filename).name,line=x.lineno,function=x.name) for x in traceback.extract_tb(exc.__traceback__)]"""
    assert source.count(a)==1;source=source.replace(a,b)
    compile(source,'factory-verified-uuid-v2','exec');return source

def configure_old():
    old.ROOT=ROOT;old.traceback=traceback
    exec(compile(fixed_run(inspect.getsource(old.run)),'factory-verified-uuid-v2','exec'),old.__dict__)

def prepare():
    assert old.sha(DONOR/'plan.json')==PIN
    p=old.read(DONOR/'plan.json');assert old.read(DONOR/'audit-v1.json')['accepted']==0
    assert all(old.sha(DONOR/n)==h for n,h in p['files'].items())
    assert all(old.sha(n)==h for n,h in p['input_files'].items())
    assert old.sha(old.IMAGE)==p['task_image_sha256']
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        if n=='run.sbatch':continue
        dest=ROOT/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dest)
    shutil.copyfile(__file__,ROOT/NAME)
    shutil.copyfile(Path(__file__).with_name('factory_integration_v2_readout_20261011.py'),ROOT/'factory_integration_v2_readout_20261011.py')
    (ROOT/'workspace/input_cache').mkdir(parents=True);(ROOT/'results').mkdir()
    batch=(DONOR/'run.sbatch').read_text().replace(str(DONOR),str(ROOT))
    assert batch.count('factory_integration_20261011.py')==1
    batch=batch.replace('factory_integration_20261011.py',NAME)
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    fixed_run(inspect.getsource(old.run))
    p.update(previous_closed_plan_sha256=PIN,intervention='Normalize host CUDA_VISIBLE_DEVICES to the SAME UUID returned by actual1-device driver check; keep senior conflict guard unchanged. Record exception frame names/lines,not values.',
        files={str(f.relative_to(ROOT)):old.sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    old.write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,planned=6,gpu_seconds_cap=900,plan_sha256=old.sha(ROOT/'plan.json'))))

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':configure_old();sys.exit(old.run())
    else:raise ValueError('mode')
