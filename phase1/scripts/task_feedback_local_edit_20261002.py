"""One-step matched output-format experiment. No search/LLM-weight update."""
import argparse,ast,copy,hashlib,importlib.util,inspect,json,os,random,secrets,shutil,sys
from pathlib import Path
OLD=Path('/research/d7/spc/yzyang4/task-feedback-upper-20261002-v1')
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-local-edit-20261002-v1')
BASE_SHA='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
base=ROOT/'v6_runtime.py' if (ROOT/'v6_runtime.py').exists() else OLD/'v6_runtime.py'
if hashlib.sha256(base.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('base drift')
spec=importlib.util.spec_from_file_location('edit_v6',base);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
m.ROOT=ROOT;m.PORT=19443;m.SECONDS=900;m.CAP=5100;m.COMMIT='ca65a10641e469846576e354d0ea512abea3498d'
m.infra.ROOT=ROOT;m.infra.SERVICE_PORT=m.PORT
def schedule():
    starts=[('random-acts-of-pizza',102201),('tweet-sentiment-extraction',102202),('random-acts-of-pizza',102203),('tweet-sentiment-extraction',102204),('random-acts-of-pizza',102205),('tweet-sentiment-extraction',102206)]
    order=list('FP');random.Random(2026100202).shuffle(order);out=[]
    for block in range(2):
        for j,arm in enumerate(order if block==0 else order[::-1]):
            for k in range(3):
                start=block*3+k;task,seed=starts[start]
                out.append(dict(index=len(out),start=start,task=task,seed=seed,arm=arm,wave=block*2+j))
    return out
m.schedule=schedule
def accounting():return dict(job=None,gpu_seconds=33034,combined_gpu_hours_cap=(33034+5*m.CAP)/3600,scope='15204+15205 plus new allocation; within16.833333333333334')
m.prior_accounting=accounting
COMMON="""You are improving an existing valid Kaggle program under a short budget.
TASK:
{{task_desc}}
CURRENT PROGRAM:
{{prev_code}}
EXECUTION:
{{prev_terminal_output}}
TRUSTED FEEDBACK, PUBLIC EVIDENCE AND HUMAN RECOMMENDATION:
{{memory}}
ENVIRONMENT:
One RTX3090, six CPUs. Installed packages: {{packages}}.
Data preview: {{data_overview}}
Execution cap: {{execution_timeout}}. Time remaining: {{time_remaining}}.
Implement one minimal change addressing the recommendation. Preserve unrelated working components, architecture, training, data paths, validation protocol and output format. Do not add model downloads or new dependencies. The public evidence is not a proof of a held-out gain. If no change is justified, retain the program. State a brief rationale before the requested output. You get one generation and one execution; no debug retry.
"""
FORMATS={
'F':"""OUTPUT FORMAT: Return exactly one fenced python block containing the complete runnable program, including unchanged portions. It must still save submission.csv in the same location. Do not emit patch blocks.""",
'P':"""OUTPUT FORMAT: Return exactly one fenced json block containing an array of at most eight objects with exactly the keys "search" and "replace", both strings. Each nonempty search string must match exactly once in the CURRENT PROGRAM at the time it is applied; preserve indentation and newlines exactly. Replacements are applied in listed order. Unmatched or ambiguous edits fail without fuzzy repair. An empty array means keep the program. This is source editing, not a shell command; do not supply a complete-program python block."""
}
def decode(raw,parent,s,action):
    from dojo.utils.code_parsing import extract_code
    from local_edit_format_20261002 import apply_response
    try:
        code,details=apply_response(raw,parent.code,s['arm'],extract_code);status='accepted'
    except (ValueError,SyntaxError,TypeError,KeyError,json.JSONDecodeError) as e:
        code='raise ValueError("Rejected generated edit format")\n';details={'error_type':type(e).__name__};status='rejected'
    m.write(action/'format.json',dict(status=status,arm=s['arm'],**details))
    return raw.split('```',1)[0]+'\n```python\n'+code+'\n```'
m.decode=decode
def adapt(name,replacements):
    src=inspect.getsource(getattr(m,name))
    for a,b in replacements:
        if src.count(a)!=1:raise ValueError('adaptation mismatch '+name+' '+a[:40])
        src=src.replace(a,b)
    exec(compile(src,'local_edit_'+name,'exec'),m.__dict__)
adapt('worker',[("TIME_LIMIT='30 minutes'","TIME_LIMIT='15 minutes'"),("STEP_LIMIT='5'","STEP_LIMIT='2'")])
adapt('episode',[('for step in range(5):','for step in range(2):'),("feedback(s['arm'],basic,pfacts,parent.plan or '')","feedback('C',basic,pfacts,parent.plan or '')"),("if s['arm']!='A':","if True:"),("plan=raw.split('```',1)[0];node=Node(code=raw","raw=decode(raw,parent,s,action)\n            plan=raw.split('```',1)[0];node=Node(code=raw")])
adapt('controller',[('03:39:00','01:24:00'),('00:33:00','00:18:00'),('for wave in range(6):','for wave in range(4):'),('dict(attempts=18,','dict(attempts=12,')])
def prepare():
    if ROOT.exists():raise FileExistsError('one-shot root exists')
    p=m.read(OLD/'plan.json')
    if m.sha(OLD/'plan.json')!='9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0':raise ValueError('parent plan drift')
    ROOT.mkdir(mode=0o700);here=Path(__file__).parent
    for rel,h in p['files'].items():
        if rel.startswith(('configs/','starts/','bin/','service-cache/')) or rel in ('task_feedback_real_20261001.py','task_feedback_facts_20261001.py','protocol.md','run.sbatch','service_entry.py'):continue
        src=OLD/rel
        if m.sha(src)!=h:raise ValueError('support drift '+rel)
        dst=ROOT/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    shutil.copyfile(here/'task_feedback_local_edit_20261002.py',ROOT/'task_feedback_real_20261001.py')
    shutil.copyfile(here/'local_edit_format_20261002.py',ROOT/'local_edit_format_20261002.py')
    shutil.copyfile(here/'FEEDBACK_LOCAL_EDIT_20261002.md',ROOT/'protocol.md')
    facts=(OLD/'task_feedback_facts_20261001.py').read_text();assert facts.count(str(OLD))==1
    (ROOT/'task_feedback_facts_20261001.py').write_text(facts.replace(str(OLD),str(ROOT)))
    for rel in ('starts','configs','bin','service-cache/tmp'):(ROOT/rel).mkdir(parents=True,exist_ok=True)
    (ROOT/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n');os.chmod(ROOT/'bin/singularity',0o700)
    entry=(OLD/'service_entry.py').read_text();assert entry.count("'19442'")==1
    (ROOT/'service_entry.py').write_text(entry.replace("'19442'","'19443'"))
    with (ROOT/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    m.setup()
    from dojo.utils.code_parsing import extract_code
    starts=[]
    for start in range(6):
        src=OLD/'starts'/f'{start}.private.json'
        if m.sha(src)!=p['files'][str(src.relative_to(OLD))]:raise ValueError('start drift')
        old=m.read(src);code=extract_code(old['code']);ast.parse(code)
        m.write(ROOT/'starts'/f'{start}.private.json',{'code':code,'plan':old['plan']})
        starts.append(dict(p['starts'][start],normalized_code_sha256=hashlib.sha256(code.encode()).hexdigest()))
    for s in schedule():
        donor=next(x for x in p['schedule'] if x['start']==s['start'] and x['arm']=='C')['index']
        cfg=m.read(OLD/f'configs/{donor}.json');ep=ROOT/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'local-edit-20261002-{s["index"]}'
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],script_id='task-feedback-local-edit-20261002',git_commit_id=m.COMMIT,base_path=str(ROOT/'source'))
        cfg['solver'].update(time_limit_secs=m.SECONDS,step_limit=2,checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter']['working_dir']=str(ep/'unused-work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(s['seed'])
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url']=f'http://127.0.0.1:{m.PORT}/v1';op['llm']['generation_kwargs']['seed']=s['seed']
            op['system_message_prompt_template']['template']=COMMON+FORMATS[s['arm']]
            op['system_message_prompt_template']['input_variables']=['task_desc','prev_code','prev_terminal_output','memory','packages','data_overview','execution_timeout','time_remaining']
        m.write(ROOT/'configs'/f'{s["index"]}.json',cfg)
    batch=(OLD/'run.sbatch').read_text().replace(str(OLD),str(ROOT)).replace('feedback-upper-ABC','feedback-local-edit').replace('03:10:00','01:25:00').replace('11340s','5040s')
    (ROOT/'run.sbatch').write_text(batch)
    files={str(q.relative_to(ROOT)):m.sha(q) for q in ROOT.rglob('*') if q.is_file() and q.name!='.service.env'}
    m.write(ROOT/'plan.json',dict(protocol='matched-local-edit-v1',base_commit=m.COMMIT,utc=m.utc(),parent_plan_sha256=m.sha(OLD/'plan.json'),schedule=schedule(),starts=starts,files=files,run_seconds=m.SECONDS,allocation_seconds=m.CAP,gpu_hours_cap=5*m.CAP/3600,prior_failed_allocation=accounting(),paid_api=0,agent_training=False,renewal='confirmed',protected_opened=False,final_evaluation=False))
    print(json.dumps({'status':'PREPARED','plan_sha256':m.sha(ROOT/'plan.json'),'planned':len(schedule()),'gpu_hours_cap':5*m.CAP/3600,'combined_cap':accounting()['combined_gpu_hours_cap']}))
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','worker','controller','service','check']);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='worker':m.worker(a.index)
    elif a.mode=='check':m.check();print('FROZEN_PLAN_VALID')
    else:getattr(m,a.mode)()
