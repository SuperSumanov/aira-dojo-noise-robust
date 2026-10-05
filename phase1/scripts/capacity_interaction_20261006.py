"""Posthoc missing-cell test on the existing Spooky positive control.

Not an equal-feature-budget algorithm comparison: the full-word union can use
75000 features. Tests whether three-cell path decomposition hides interaction.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import matched_representation_20261005 as runner

B=Path('/research/d7/spc/yzyang4')
DONOR=B/'vocabulary-capacity-20261006-v1'
R=B/'capacity-interaction-20261006-v1'
THIS=Path(__file__).name
PY=B/'venvs/aira/bin/python'
read,write,sha=runner.read,runner.write,runner.sha
TASK='spooky-author-identification'

OVERRIDE='''
def vectors(arm, p):
    assert arm in ('word_char', 'word50_char')
    return [TfidfVectorizer(ngram_range=(1,p['ngram']),min_df=p['min_df'],max_features=50000 if arm=='word50_char' else 25000,sublinear_tf=True,dtype=np.float64),
            TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=p['min_df'],max_features=25000,sublinear_tf=True,dtype=np.float64)]
'''


def schedule():
    rows=[]
    for j,seed in enumerate(runner.SEEDS):
        for arm in (('word_char','word50_char') if j==0 else ('word50_char','word_char')):
            rows.append(dict(index=len(rows),task=TASK,task_index=1,seed=seed,arm=arm))
    return rows


def configure():
    runner.R,runner.NAME,runner.PROGRAM=R,THIS,'program.py'
    runner.schedule=schedule
    runner.DONOR_SHA=sha(R/'runtime.py')


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and not R.exists()
    assert sha(DONOR/'plan.json')=='acf546f7b5430910c6a695eeabfbff0cb5a4f27d3dd5d89e9f4c680e7a045e84'
    assert (DONOR/'closed.json').exists()
    old=read(DONOR/'plan.json')
    for rel,h in old['files'].items():assert sha(DONOR/rel)==h,rel
    R.mkdir(mode=0o700)
    for rel in old['files']:
        if rel.startswith(('source/','forets_','opencl-vendors/')) or rel in ('runtime.py','matched_representation_20261005.py'):
            dst=R/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/rel,dst)
    shutil.copyfile(__file__,R/THIS)
    program=(DONOR/'capacity_program.py').read_text()+'\n'+OVERRIDE
    compile(program,'program.py','exec');(R/'program.py').write_text(program)
    (R/'configs').mkdir();(R/'bin').mkdir()
    wrapper=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(THIS).stem} import configure,runner\nconfigure()\nrunner.runtime().task_runtime()\n'
    (R/'bin/singularity').write_text(wrapper);os.chmod(R/'bin/singularity',0o700)
    for row in schedule():
        donor=next(x for x in old['schedule'] if x['task']==TASK and x['seed']==row['seed'] and x['arm']=='word_char')
        c=read(DONOR/'configs'/f"{donor['index']}.json");ep=R/f"episode-{row['index']}";ep.mkdir()
        c['id']=f"capacity-interaction-{row['index']}";c['logger']['output_dir']=str(ep/'native-log')
        c['metadata'].update(base_path=str(R/'source'),git_commit_id=commit,script_id='capacity-interaction-20261006')
        c['task'].update(cache_dir=str(R/'no-official-data'),results_output_dir=str(ep/'native-log/results'))
        c['interpreter']['working_dir']=str(ep/'action-0/work')
        write(R/'configs'/f"{row['index']}.json",c)
    batch=f'''#!/bin/bash
#SBATCH --job-name=capacity-interaction
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 2340s {PY} -B {R}/{THIS} controller
'''
    (R/'run.sbatch').write_text(batch)
    write(R/'plan.json',dict(protocol='capacity-interaction-posthoc-missing-cell-v1',source_commit=commit,
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()},schedule=schedule(),
        donor_plan_sha256=sha(DONOR/'plan.json'),grid=old['grid'],task_selection='Spooky selected posthoc for the clear capacity-ablation signal; not unbiased across-task confirmation',
        primary='paired word50_char versus word_char; lower logloss better',
        secondary='interaction: word-capacity gain with characters minus the prior word-capacity gain without characters; keep the donor analysis unchanged',
        budget='Same grid/solver/split/caps; feature maximum changes 50000 to 75000 by design. NOT equal feature budget, full cost or an autonomous method gain.',
        no_generator=True,no_paid_api=True,no_base_training=True,protected_opened=False,automatic_expansion=False,
        assigned=4,classifier_fits_planned=116,binary_fits_planned=348,program_seconds=360,worker_seconds=440,
        gpus=1,allocation_seconds=2400,gpu_hours_cap=2400/3600,stopping='Four slots only; preserve every missing/failed slot; no resampling or retry.',
        limitations='Posthoc reused development task/splits, known human-chosen representation. Old pure-word cells reused only with exact source/split identity, never replacing a missing new union endpoint.'))
    configure();runner.runtime()
    from dojo.config_dataclasses.run import RunConfig
    for row in schedule():
        c=RunConfig.load_from_json(R/'configs'/f"{row['index']}.json");c.validate()
        assert not Path(c.task.private_dir).exists() and not c.interpreter.read_only_binds
        assert sha(c.task.search_only_dev_scorer_path)==c.task.search_only_dev_scorer_sha256
        assert c.task.data_dir==c.task.public_dir and '/search-only-dev-' in c.task.data_dir
    m=runner.load('interaction_synthetic',R/'program.py')
    for arm,cap in [('word_char',25000),('word50_char',50000)]:
        vs=m.vectors(arm,dict(ngram=2,min_df=1));assert [v.max_features for v in vs]==[cap,25000]
        x,z=m.design(vs,['alpha beta','beta gamma','gamma delta'],['unknownqq alpha'])
        assert all('unknownqq' not in v.vocabulary_ for v in vs)
        assert m.np.allclose(m.np.asarray(x.multiply(x).sum(1)).ravel(),1)
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(status='PASS',typed_configs=4,plan_sha256=sha(R/'plan.json'),task_image_sha256=read(DONOR/'preflight.json')['task_image_sha256']))
    print(json.dumps(dict(status='PREPARED',assigned=4,plan_sha256=sha(R/'plan.json'))))


def controller():
    configure();runner.check();m=runner.runtime();assert read(R/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    codes=[]
    for row in schedule():
        ep=R/f"episode-{row['index']}";assert not (ep/'native.json').exists()
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:08:00',str(PY),'-B',str(R/THIS),'worker','--index',str(row['index'])]
        with (ep/'worker.private.log').open('xb') as f:q=subprocess.run(cmd,env=m.infra().clean_env(),stdout=f,stderr=f)
        write(ep/'closed.json',dict(returncode=q.returncode));codes.append(q.returncode)
    write(R/'closed.json',dict(returncodes=codes,assigned=4))


if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','worker','controller','check','tests']);p.add_argument('--commit');p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='tests':
        assert len(schedule())==4 and len({(x['seed'],x['arm']) for x in schedule()})==4
        compile(OVERRIDE,'override','exec');print('INTERACTION_STATIC_PASS assigned=4 fits=116 binary_fits=348')
    elif a.mode=='prepare':prepare(a.commit)
    elif a.mode=='controller':controller()
    else:
        configure()
        if a.mode=='worker':runner.worker(a.index)
        else:getattr(runner,a.mode)()
