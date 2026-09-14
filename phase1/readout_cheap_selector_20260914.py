"""All-closed three-arm final-quality readout and independent selector replay."""
import argparse,csv,json,math,os,sqlite3,statistics,sys
from pathlib import Path
from forets_environment_build_20260912 import read,write,encode,sha
from read_forets_action_delivery_20260913 import read_latest
from verify_cheap_selector_20260914 import independent_selection

FILES=('readout_cheap_selector_20260914.py','readout_cheap_selector_core_20260914.py','verify_cheap_selector_20260914.py',
    'read_forets_action_delivery_20260913.py','readout_forets_generation_capacity_20260912.py')
TASKS=('leaf-classification','spaceship-titanic');ARMS=('uniform','short_code','learned_validity');SEEDS=(46,47)
def comparisons(rows):
    if len(rows)!=12 or {(r['task'],r['seed'],r['arm']) for r in rows}!={(t,s,a) for t in TASKS for s in SEEDS for a in ARMS}:raise ValueError('complete fixed matrix')
    for r in rows:
        for name in ('technical_eligible','action_valid','iteration_valid'):
            if type(r[name]) is not bool:raise ValueError('Boolean qualification required')
        for endpoint in ('action','iteration'):
            value=r[endpoint+'_score']
            if r[endpoint+'_valid']:
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('finite valid score')
            elif value is not None:raise ValueError('missing score cannot be filled')
    pairs=[];groups=[]
    for endpoint in ('action','iteration'):
        for baseline in ARMS[:2]:
            for task in TASKS:
                pp=[]
                for seed in SEEDS:
                    a,b=[next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,arm)) for arm in (baseline,'learned_validity')]
                    technical=a['technical_eligible'] and b['technical_eligible'];av=a[endpoint+'_valid'];bv=b[endpoint+'_valid']
                    gain=((a[endpoint+'_score']-b[endpoint+'_score']) if task==TASKS[0] else (b[endpoint+'_score']-a[endpoint+'_score'])) if technical and av and bv else None
                    sign=(int(bv)-int(av) if av!=bv else (int(gain>0)-int(gain<0) if gain is not None else 0)) if technical else None
                    rec=dict(endpoint=endpoint,baseline=baseline,task=task,seed=seed,technical_comparable=technical,baseline_valid=av,learned_valid=bv,gain=gain,sign=sign)
                    pairs.append(rec);pp.append(rec)
                vals=[p['gain'] for p in pp if p['gain'] is not None]
                groups.append(dict(endpoint=endpoint,baseline=baseline,task=task,wins=sum(p['sign']==1 for p in pp),ties=sum(p['sign']==0 for p in pp),losses=sum(p['sign']==-1 for p in pp),unknown=sum(p['sign'] is None for p in pp),median_gain=statistics.median(vals) if vals else None,sample_sd_gain=statistics.stdev(vals) if len(vals)>1 else None))
    primary=[g for g in groups if g['endpoint']=='action']
    gate=all(r['technical_eligible'] for r in rows) and all(g['wins']>=g['losses'] for g in primary) and all(sum(g['wins']-g['losses'] for g in primary if g['baseline']==b)>0 for b in ARMS[:2])
    return dict(pairs=pairs,groups=groups,investment_gate=gate)
def main(root):
    root=root.resolve(strict=True);build=read(root/'build.json');plan=read(root/'readout-plan.json')
    if (plan['root'],plan['source_tree'],plan['prepared_sha256'])!=(str(root),build['source_tree'],build['prepared_sha256']):raise ValueError('reader binding')
    if set(plan['readers'])!=set(FILES):raise ValueError('reader inventory')
    for n,h in plan['readers'].items():
        if sha(Path(__file__).with_name(n).read_bytes())!=h:raise ValueError('frozen reader drift')
    write(root/'readout-intent.json',encode(dict(plan_sha256=sha((root/'readout-plan.json').read_bytes()))))
    import readout_cheap_selector_core_20260914 as core
    core.verify(root,seeds=SEEDS,blocks=(1,2))
    base=read(root/'wallclock-summary.json');prepared=read(root/'prepared.json',build['prepared_sha256'])
    sys.path[:0]=[str(root/'source/src'),str(root/'code')]
    from dojo.core.solvers.utils.response import extract_code
    from dojo.solvers.fore_ts.cheap_ranker import MODEL_PATH,MODEL_SHA
    # Features independently implemented in the pre-existing model verifier.
    import ast,collections,warnings,numpy as np,joblib,io
    modelraw=Path(MODEL_PATH).read_bytes()
    if sha(modelraw)!=MODEL_SHA:raise ValueError('model drift')
    model=joblib.load(io.BytesIO(modelraw))['model']
    types=('Import','ImportFrom','Call','FunctionDef','ClassDef','For','While','If','Try','With','Assign','Subscript','Attribute','ListComp','DictComp','Lambda','Return','Raise','ExceptHandler','Constant','Name','Compare','BinOp','BoolOp')
    def feats(code):
        code=code[:30000];bad=0;depth=0;counts=collections.Counter()
        def dep(n):return max([0]+[1+dep(c) for c in ast.iter_child_nodes(n)])
        try:
            with warnings.catch_warnings():warnings.simplefilter('ignore',SyntaxWarning);tree=ast.parse(code)
            counts.update(type(n).__name__ for n in ast.walk(tree));depth=dep(tree)
        except SyntaxError:bad=1
        return [math.log1p(len(code)),math.log1p(code.count('\n')+1),bad,depth]+[math.log1p(counts[n]) for n in types]
    from mlebench.registry import registry
    import pandas as pd
    registry=registry.set_data_dir(root.parent/'mle-bench-data');answers={};rows=[];replays=[]
    for r in base['rows']:
        pr=next(p for p in prepared['run_configs'] if p['run_id']==r['run_id']);cfg=read(root/'configs'/(r['run_id']+'.json'),pr['config_sha256']);s=cfg['solver'];cp=Path(s['checkpoint_path'])
        if (s['num_children'],s['num_children_to_choose'],s['critic_top_k'],s['time_limit_secs'],s['edit_scope'])!=(2,1,1,600,'whole_program'):raise ValueError('actual selector contract')
        if list((cp/'forets-contextual-judge-private').glob('batch-*/request-*.json')):raise ValueError('unexpected paid ranker')
        counts=dict(pools=0,selected_pools=0,candidate_executions=0,generated_including_start=0)
        for p in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(p.read_bytes())
            with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as db:raw,digest=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
            if sha(raw.encode())!=digest or sha(p.read_bytes())!=before:raise ValueError('pool drift')
            v=json.loads(raw);cs=v['candidates'];binding=v['binding'];n=len(cs);counts['pools']+=1
            counts['generated_including_start']+=sum(isinstance(c.get('node'),dict) for c in cs)
            if binding['task']!=r['task'] or binding['cheap_ranker']!=s['cheap_ranker'] or binding['selection_policy']!=s['selection_policy']:raise ValueError('binding')
            if v['selected'] is None:
                if v['task_calls']:raise ValueError('unselected executed')
                continue
            counts['selected_pools']+=1;codes=[c['node']['code'] for c in cs]
            bypass=s['skip_redundant_critic'] and r['arm']!='uniform' and n<=1
            scores=None
            if r['arm']!='uniform' and not bypass:
                scores=[c['score'] for c in cs];receipt=read(cp/'forets-cheap-ranker-private'/f"batch-{binding['step']}.json")
                expected=[float(-len(c[:30000])) for c in codes] if r['arm']=='short_code' else [float(v) for v in model.predict_proba(np.array([feats(c) for c in codes]))[:,1]]
                if scores!=expected or receipt['scores']!=scores or receipt['codes_sha256']!=[sha(c.encode()) for c in codes]:raise ValueError('independent model/length output')
            elif any(c['score'] is not None for c in cs):raise ValueError('unexpected score')
            selected=independent_selection(n,scores,r['seed'],r['task'],binding['step'])
            if v['selected']!=selected:raise ValueError('selection replay')
            originals=[];last=None;previous=None
            for call in v['task_calls']:
                if previous is not None and previous['state']!='returned':raise ValueError('call after unfinished')
                if call['intent']['role']=='candidate':
                    if originals or call['slot']!=selected[0]:raise ValueError('extra candidate execution')
                    originals.append(call);last=call['slot']
                    if call['intent']['code_sha256']!=sha(extract_code(codes[last]).encode()):raise ValueError('native code delivery')
                elif call['intent']['role']!='debug' or last is None or call['slot']!=last:raise ValueError('debug lineage')
                previous=call
            if v['phase']=='complete' and (len(originals)!=1 or any(c['state']!='returned' for c in v['task_calls'])):raise ValueError('complete ledger mismatch')
            counts['candidate_executions']+=len(originals);replays.append(dict(run_id=r['run_id'],pool=p.name,sha256=before,selected=selected))
        row=dict(r,iteration_valid=r['valid'],iteration_score=r['score'],action_valid=False,action_score=None,action_code_sha256=None,**counts)
        if r['search_start_ns'] is not None:
            data=read_latest(root/'incumbents'/r['run_id'],start_ns=r['search_start_ns'],seconds=600)
            if data is not None and data['submission'] is not None:
                receipt=data['submission'];archive=Path(receipt['archive_dir']);expected=Path(cfg['task']['results_output_dir'])/'submission-escrow'
                if archive.is_symlink() or archive.parent.resolve()!=expected.resolve():raise ValueError('action archive')
                complete=read(archive/'complete.json')
                if any(receipt.get(k)!=v for k,v in complete.items()):raise ValueError('receipt binding')
                for name,key in (('submission.csv','submission_sha256'),('report.json','report_sha256')):
                    if sha((archive/name).read_bytes())!=receipt[key]:raise ValueError('action artifact drift')
                report=read(archive/'report.json')
                if report['valid_submission'] is not True:raise ValueError('invalid selected action')
                if r['task'] not in answers:answers[r['task']]=pd.read_csv(registry.get_competition(r['task']).answers)
                independent=core.numerical(r['task'],pd.read_csv(archive/'submission.csv'),answers[r['task']])
                if round(independent,5)!=report['score']:raise ValueError('independent action grade')
                row.update(action_valid=True,action_score=report['score'],action_code_sha256=receipt['code_sha256'])
        rows.append(row)
    result=dict(role='cheap_selector_three_arm_development',source_tree=build['source_tree'],controller_commit=build['commit'],rows=rows,**comparisons(rows),selection_replays=replays,
        billing=base['billing'],allocation_gpu_hours=base['allocation_gpu_hours'],primary='action',secondary='iteration',limitation='Four task-seed triples, development pilot; no confirmatory significance or novel failure-prediction algorithm claim.')
    digest=write(root/'cheap-selector-summary.json',encode(result))
    with (root/'cheap-selector-runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(root/'readout-finished.json',encode(dict(status='verified',source_tree=build['source_tree'],summary_sha256=digest,files={n:sha((root/n).read_bytes()) for n in ('wallclock-summary.json','wallclock-runs.csv','cheap-selector-summary.json','cheap-selector-runs.csv')})))
    print(json.dumps(dict(summary_sha256=digest,groups=result['groups'],investment_gate=result['investment_gate'],allocation_gpu_hours=result['allocation_gpu_hours'])))
if __name__=='__main__':p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();os.umask(0o077);main(a.root)
