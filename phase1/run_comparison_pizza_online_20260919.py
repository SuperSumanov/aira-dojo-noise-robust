"""New task, same frozen rescue policy and budget; no cached outcome selection."""
import argparse,copy,hashlib,json,os,re,subprocess,tarfile,time
from pathlib import Path,PurePosixPath
import run_comparison_online_continuation_20260919 as driver

PREFIX=driver.BASE/'comparison-pizza-prefix-20260919-0guhqznb'
SUMMARY='b3fff2aa4228b7b09e82296c0f3929e4fa7b9083a6bb510cdfcef63f28ddaa29'
RUNS={1:'5c3f818a9595bd79',2:'1eee3186d26dcbcd'}
CONFIG={1:'4d6c28270e919f607537ca78467b73ce85f6c7a23e92195dcfff097d72e470f0',2:'2131b8994f1991c23e4cb6bd1ee997da3d2ffcdc18204b3b4d2ec197534737f2'}
CHOOSE_ORIGINAL_SECOND=False

def configure():
    driver.SCRIPT=Path(__file__).name
    driver.TASK='random-acts-of-pizza';driver.ROOT_PREFIX='comparison-pizza-full-deadline-20260919-'
    driver.FULL_DEADLINE=True
    driver.CONTEXT_MODULE='run_comparison_pizza_online_20260919'
    driver.PLAN='comparison_pizza_online_plan_20260919.json'
    driver.FILES=(driver.SCRIPT,driver.PLAN,'run_comparison_online_continuation_20260919.py','local_generator_runtime_20260914.py','run_comparison_live_debug_20260919.py','comparison_full_deadline_policy_20260919.py')
    driver.inputs=inputs

def inputs():
    rt=driver.rt
    if rt.sha(PREFIX/'summary.json')!=SUMMARY:raise ValueError('closed prefix identity')
    summary=rt.read(PREFIX/'summary.json');supplement=rt.read(PREFIX/'prefix-format-supplement.json')
    if supplement['source_summary_sha256']!=SUMMARY or supplement['all_core_errors_match'] is not True:raise ValueError('exact prefix core match')
    base=driver.BASE/'comparison-quarantine-20260919-_tda9fh6'
    raw=(base/'qwen-readout-v1/nodes.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!='370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9':raise ValueError('admitted nodes')
    # Only structural identity fields participate in pool choice; no scores are inspected.
    nodes=json.loads(raw);wanted={};cached={};prefixes={}
    for seed,run in RUNS.items():
        row,=[r for r in summary['rows'] if r['seed']==seed]
        prefixes[seed]=row;wanted[row['node']]=row['raw_code_sha256']
        if CHOOSE_ORIGINAL_SECOND:
            pool=sorted([r for r in nodes if r['run']==run and r['group']=='executed' and r['parents']==[0] and 'draft' in r['operators_used']],key=lambda r:r['step'])
            if len(pool)!=2 or pool[0]['step']!=1:raise ValueError('original two chosen siblings')
            node=pool[1]
        else:
            pool=sorted([r for r in nodes if r['run']==run and r['group']=='unselected' and r['parents']==[0] and 'draft' in r['operators_used']],key=lambda r:(r['creation_time'],r['id']))
            selected=driver.select_cache([dict(node=r['id'],index=i,role='cache') for i,r in enumerate(pool)],seed)
            node=next(r for r in pool if r['id']==selected['node'])
        cached[seed]=node;wanted[node['id']]=node['code_sha256']
    originals={};configs={}
    with tarfile.open(base/'archives/random-acts-of-pizza.tar.gz','r|gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if not member.isfile():continue
            run=hashlib.sha256(str(path.parent if path.name=='dojo_config.json' else path.parent.parent).encode()).hexdigest()[:16]
            if run not in RUNS.values():continue
            seed=next(k for k,v in RUNS.items() if v==run)
            if path.name=='dojo_config.json':
                raw=archive.extractfile(member).read()
                if hashlib.sha256(raw).hexdigest()!=CONFIG[seed] or rt.SHAPES.search(raw):raise ValueError('config identity/security')
                configs[seed]=json.loads(raw)['solver']
            elif path.name in ('journal.jsonl','journal_for_unselected.jsonl'):
                for line in archive.extractfile(member):
                    if rt.SHAPES.search(line):raise ValueError('credential-first')
                    n=json.loads(line)
                    if n.get('id') in wanted:
                        if n['id'] in originals or hashlib.sha256((n.get('code') or '').encode()).hexdigest()!=wanted[n['id']]:raise ValueError('node identity')
                        originals[n['id']]=n
    if set(originals)!=set(wanted) or set(configs)!={1,2}:raise ValueError('complete source')
    # Native extraction only; no execution/model request here.
    import sys
    sys.path.insert(0,str(rt.ASSETS/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    description=(driver.BASE/'mle-bench-data/random-acts-of-pizza/prepared/public/description.md').read_text()
    if rt.SHAPES.search(description.encode()):raise ValueError('description security')
    cases=[]
    for seed in (1,2):
        row=prefixes[seed];cfg=configs[seed];n=originals[row['node']]
        if cfg['use_test_score'] is not False or cfg['max_debug_depth']!=20 or cfg['num_children']!=6 or cfg['critic_top_k']!=3:raise ValueError('original protocol')
        log=PREFIX/f'output-{row["index"]}.private.log'
        if rt.sha(log)!=row['log_sha256']:raise ValueError('fresh prefix log')
        rawcache=originals[cached[seed]['id']]['code']
        if re.search(r'/prepared/private|/data/private|/research/[^\s\"\x27]+',rawcache):raise ValueError('unapproved path')
        code=extract_code(rawcache)
        sampling=cfg['operators']['debug']['llm']['generation_kwargs']
        if sampling.get('temperature')!=.6 or sampling.get('top_p')!=.95:raise ValueError('debug sampling')
        case=dict(seed=seed,run=RUNS[seed],node=row['node'],code=n['code'],term_out=log.read_text(),raw_code_sha256=row['raw_code_sha256'],
            log_sha256=row['log_sha256'],config_sha256=CONFIG[seed],operator=copy.deepcopy(cfg['operators']['debug']),
            analysis_operator=copy.deepcopy(cfg['operators']['analyze']),analysis_sampling={k:cfg['operators']['analyze']['llm']['generation_kwargs'].get(k) for k in ('temperature','top_p')},
            solver={k:cfg[k] for k in ('available_packages','execution_timeout','step_limit','data_preview')},debug_memory=cfg['debug_memory'],
            description=description,description_sha256=hashlib.sha256(description.encode()).hexdigest(),plan=n.get('plan'),analysis=n.get('analysis'),lower_is_better=False,
            cache=dict(code=code,code_sha256=hashlib.sha256(code.encode()).hexdigest(),node=cached[seed]['id']))
        cases.append(case)
    return cases

def binding_context(env):
    configure();return driver.binding_context(env)

if __name__=='__main__':
    os.umask(0o077);configure();parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','cpu','submit','controller','server','bounded-worker','episode']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--lane',type=int);parser.add_argument('--index',type=int);a=parser.parse_args()
    if a.mode=='prepare':driver.prepare(a.commit)
    elif a.mode=='server':driver.check(a.root);driver.rt.ROOT=a.root/f'lane-{a.lane}';driver.rt.server()
    elif a.mode=='bounded-worker':
        start=driver.rt.read(a.root/f'episode-{a.index}/start.json');left=max(1,start['monotonic']+driver.EPISODE-time.monotonic())
        raise SystemExit(subprocess.call(['timeout','--signal=TERM','--kill-after=10s',str(left)+'s',str(driver.rt.PYTHON),'-B',str(a.root/driver.SCRIPT),'episode','--root',str(a.root),'--index',str(a.index)]))
    elif a.mode=='episode':driver.episode(a.root,a.index)
    else:getattr(driver,a.mode)(a.root)
