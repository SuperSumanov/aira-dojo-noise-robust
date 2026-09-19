"""Single closed readout of frozen online rescue episodes. No oracle selection."""
import argparse,csv,hashlib,json,math,os,re,statistics,subprocess,sys
from pathlib import Path
import local_generator_runtime_20260914 as rt
ROOT=rt.BASE/'comparison-online-continuation-20260919-qpw9ys94'
PREPARED='99cff06463fa986bfa6a5d732d81cc1b392b4d08b61a194bf78c12cd4bc9783b'
BUDGET=2100
TASK='spooky-author-identification'
METRIC_DELTA='loss_delta_cache_minus_baseline'
NUMERICAL=None
ROLE='live_conditioned_rescue_not_full_e2e'
EPISODE_AUDIT=None
LATENCY_FIELD='accepted_seconds'
OUTPUT_ROOT=None
READOUT_CONTEXT={}


def read_metric_frame(path):
    """Match MLE-bench's documented float input semantics, not its metric code."""
    import pandas as pd
    return pd.read_csv(path,float_precision='round_trip')

def safe(path,expected=None):
    raw=path.read_bytes()
    if path.is_symlink() or (expected and hashlib.sha256(raw).hexdigest()!=expected) or rt.SHAPES.search(raw):raise ValueError('identity/security')
    return json.loads(raw)

def closed_allocation(job):
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
    row,=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==job]
    if row[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'}:raise ValueError('allocation still active')
    if row[3]!='gpu28' or dict(p.split('=',1) for p in row[4].split(','))['gres/gpu']!='6':raise ValueError('hardware/resources')
    return dict(job=job,state=row[1],seconds=int(row[2]),gpus=6,gpu_hours=int(row[2])*6/3600)

def compare(rows,metric_delta='loss_delta_cache_minus_baseline',latency_field='accepted_seconds'):
    if len(rows)!=4 or {r['index'] for r in rows}!={0,1,2,3}:raise ValueError('fixed four episodes')
    groups=[]
    for seed in (1,2):
        pair=[r for r in rows if r['seed']==seed]
        if len(pair)!=2 or {r['cache'] for r in pair}!={False,True}:raise ValueError('pair identity')
        baseline=next(r for r in pair if not r['cache']);cache=next(r for r in pair if r['cache'])
        known=all(r['valid_accepted_submission'] is not None for r in pair)
        group=dict(seed=seed,baseline_valid=baseline['valid_accepted_submission'],cache_valid=cache['valid_accepted_submission'])
        if not known:group['status']='UNKNOWN_NO_EFFECT_CLAIM'
        else:
            delta=int(cache['valid_accepted_submission'])-int(baseline['valid_accepted_submission'])
            both=cache['valid_accepted_submission'] and baseline['valid_accepted_submission']
            group.update(status='CLOSED_EXPLORATORY_EPISODE_PAIR',validity_delta=delta,
                first_accept_seconds_delta=(cache[latency_field]-baseline[latency_field]) if both else None)
            group[metric_delta]=(cache['score']-baseline['score']) if both else None
        groups.append(group)
    return dict(physical_runs=2,groups=groups,
        paired_validity_mean_delta=statistics.mean(g['validity_delta'] for g in groups) if all('validity_delta' in g for g in groups) else None,
        limitation='Two seen development prefixes; no population significance, complete-search improvement, paid-cost reduction, or independent confirmation is established.')

def main(reader_commit):
    if not re.fullmatch('[a-f0-9]{40}',reader_commit):raise ValueError('reader commit')
    p=safe(ROOT/'prepared.json',PREPARED)
    for name,digest in p['files'].items():
        if rt.sha(ROOT/name)!=digest:raise ValueError('frozen input drift')
    if p['episode_seconds']!=BUDGET or p['gpu_hours_cap']!=10 or p['task']!=TASK:raise ValueError('frozen budget/task')
    job=safe(ROOT/'launch.json')['job'];allocation=closed_allocation(job)
    closure=safe(ROOT/'closed.json') if (ROOT/'closed.json').exists() else {'status':'absent'}
    complete=closure['status']=='all_four_episodes_closed'
    output=ROOT if OUTPUT_ROOT is None else OUTPUT_ROOT
    if output!=ROOT:output.mkdir(exist_ok=False)
    rt.write(output/'readout-claim.json',dict(reader_commit=reader_commit,reader_sha256=rt.sha(Path(__file__)),prepared_sha256=PREPARED,utc=rt.utc(),context=READOUT_CONTEXT))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',MLE_BENCH_DATA_DIR=str(rt.BASE/'mle-bench-data'),LOGGING_DIR=str(ROOT))
    sys.path.insert(0,str(rt.ASSETS/'source/src'))
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    if NUMERICAL is None:
        from readout_comparison_spooky_pool_20260919 import numerical
    else:numerical=NUMERICAL
    import pandas as pd
    competition=registry.set_data_dir(rt.BASE/'mle-bench-data').get_competition(TASK)
    services=[]
    if (ROOT/'services-ready.json').exists():
        services=safe(ROOT/'services-ready.json')['uuids']
        if len(set(services[0]+services[1]))!=4:raise ValueError('server overlap')
    rows=[];wave_devices={};truth=None
    for index in range(4):
        seed=index//2+1;lane=index%2;ep=ROOT/f'episode-{index}'
        row=dict(index=index,seed=seed,lane=lane,cache=lane==index//2,budget_seconds=BUDGET,
            status='infrastructure_unknown',valid_accepted_submission=None,score=None,independent_score=None,accepted_seconds=None,
            source_commit=p['commit'],job=job,action_count=0,model_calls_completed=0,debug_completion_tokens_recorded=0)
        if not complete or not (ep/'start.json').exists():rows.append(row);continue
        start=safe(ep/'start.json')
        if any(start[k]!=row[k] for k in ('index','seed','lane','cache','budget_seconds')):raise ValueError('episode identity')
        wave=safe(ROOT/f'wave-{index//2}.json');returncode=wave['returncodes'][lane]
        finished=safe(ep/'finished.json') if (ep/'finished.json').exists() else None
        if returncode not in (0,124,137,143):rows.append(row);continue
        if returncode==0 and finished is None:raise ValueError('successful worker without closure')
        actions=[]
        for file in sorted(ep.glob('action-*.json'),key=lambda f:int(f.stem.split('-')[1])):
            action=safe(file);actions.append(action)
            for name in ('generation_usage',):
                usage=action.get(name) or {};row['debug_completion_tokens_recorded']+=usage.get('completion_tokens') or 0
        row['action_count']=len(actions);row['model_calls_completed']=len(list(ep.glob('generation-*.private.json')))+len(list(ep.glob('analysis-*.private.json')))
        # Analyze response payloads and raw programs are not emitted or used to select.
        for action_index,action in enumerate(actions):
            if action.get('binding_sha256'):
                binding=safe(ep/f'identity-{action_index}.native-binding.json',action['binding_sha256'])
                native=binding['native_identity'];device=native['selected_uuid']
                if native['job']!=job or binding['namespace']['exact_device_namespace'] is not True:raise ValueError('native task isolation')
                if device in services[0]+services[1]:raise ValueError('task and generator overlap')
                wave_devices.setdefault(index,set()).add(device)
        if len(wave_devices.get(index,set()))>1:raise ValueError('worker switched GPU mid-episode')
        if EPISODE_AUDIT is not None:row.update(EPISODE_AUDIT(ep,actions,start,finished))
        if finished and finished['status']=='unknown':rows.append(row);continue
        row.update(status=finished['status'] if finished else 'hard_deadline',valid_accepted_submission=False,
                   elapsed_seconds=finished['elapsed_seconds'] if finished else BUDGET,worker_returncode=returncode)
        incumbent_path=ep/'incumbent.json'
        if incumbent_path.exists():
            incumbent=safe(incumbent_path);i=incumbent['action_index']
            if not (0<=incumbent['accepted_seconds']<=BUDGET) or i>=len(actions):raise ValueError('late/incomplete incumbent')
            action=actions[i]
            if action.get('native_accepted') is not True or action.get('submission_sha256')!=incumbent['submission_sha256']:raise ValueError('incumbent identity')
            row['accepted_seconds']=incumbent['accepted_seconds'];row['incumbent_code_sha256']=incumbent['code_sha256']
            submission=ep/f'work-{i}/submission.csv'
            if submission.is_symlink() or rt.sha(submission)!=incumbent['submission_sha256']:raise ValueError('submission drift')
            valid,_=validate_submission(submission,competition)
            if valid:
                grade_dir=ep/'closed-grade' if output==ROOT else output/f'episode-{index}-closed-grade'
                grade,_=evaluate_submission(submission,rt.BASE/'mle-bench-data',TASK,grade_dir)
                if grade is not None and math.isfinite(float(grade)):
                    if truth is None:truth=read_metric_frame(competition.answers)
                    numeric=numerical(TASK,read_metric_frame(submission),truth)
                    if round(numeric,5)!=float(grade):raise ValueError('independent numerical grade')
                    row.update(valid_accepted_submission=True,score=float(grade),independent_score=numeric)
            if rt.sha(submission)!=incumbent['submission_sha256']:raise ValueError('submission changed while grading')
        rows.append(row)
    for wave in (0,1):
        if wave_devices.get(wave*2,set()) & wave_devices.get(wave*2+1,set()):raise ValueError('concurrent worker overlap')
        if (ROOT/f'episode-{wave*2}/start.json').exists() and (ROOT/f'episode-{wave*2+1}/start.json').exists():
            a=safe(ROOT/f'episode-{wave*2}/start.json');b=safe(ROOT/f'episode-{wave*2+1}/start.json')
            if a['monotonic']!=b['monotonic']:raise ValueError('unequal start clock')
    result=dict(role=ROLE,utc=rt.utc(),prepared_sha256=PREPARED,
        reader_commit=reader_commit,reader_sha256=rt.sha(Path(__file__)),allocation=allocation,closure=closure['status'],rows=rows,
        task=TASK,metric_delta_field=METRIC_DELTA,latency_field=LATENCY_FIELD,comparison=compare(rows,METRIC_DELTA,LATENCY_FIELD),external_grades_read_only_after_closure=True,paid_api_calls=0,model_training=False,
        numeric_csv_precision='round_trip',readout_context=READOUT_CONTEXT)
    rt.write(output/'summary.json',result)
    with (output/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({k for row in rows for k in row}));writer.writeheader();writer.writerows(rows)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reader-commit',required=True);main(parser.parse_args().reader_commit)
