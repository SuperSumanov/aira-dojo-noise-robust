"""One prelaunch source-commit closure; forbidden once a job was requested.

Preserves preparation receipts. Changes no dataset, configuration, seed or arm.
Only freezes final readout/tests and the commit of this new batch before GPU use.
"""
import re,shutil,subprocess,sys
from pathlib import Path
from lifecycle_pilot import read,write,sha
import image_live_2plus4_20261011 as trial

def freeze(commit):
    r=trial.R
    assert re.fullmatch('[a-f0-9]{40}',commit)
    assert not (r/'submit-intent.json').exists() and not (r/'launch.json').exists()
    assert not any(r.glob('episode-*/deadline.json'))
    p=read(r/'plan.json');old=read(r/'cpu.json');assert old['plan_sha256']==sha(r/'plan.json')
    assert all(sha(r/n)==h for n,h in p['files'].items())
    archive=r/'prelaunch-preparation';archive.mkdir()
    shutil.move(r/'plan.json',archive/'plan.json');shutil.move(r/'cpu.json',archive/'cpu.json')
    for n in ('test_image_live_20261011.py','image_live_readout_20261011.py','live_readout.py','freeze_image_live_20261011.py'):
        shutil.copyfile(Path(__file__).with_name(n),r/n);p['files'][n]=sha(r/n)
    p['source_parent_commit']=p['source_commit'];p['source_commit']=commit
    p['prelaunch_preparation_sha256']=sha(archive/'plan.json')
    write(r/'plan.json',p)
    trial.cpu()
    result=subprocess.run([str(trial.PY),'-B','-m','unittest','test_image_live_20261011','-v'],cwd=r,check=True)
    write(r/'prelaunch-source-closure.json',dict(source_commit=commit,plan_sha256=sha(r/'plan.json'),
        fixed_data_and_configs=True,assigned=32,source_tests_exit=result.returncode,old_plan_sha256=p['prelaunch_preparation_sha256']))
    print({'frozen_commit':commit,'plan_sha256':sha(r/'plan.json'),'assigned':32,'gpu_hours_cap':17})

if __name__=='__main__':freeze(sys.argv[1])
