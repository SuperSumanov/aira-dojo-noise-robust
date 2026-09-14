"""Old completed pools only: quality stress test, no new policy or fitting."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
os.environ['PYTHON_DOTENV_DISABLED']='1'
from collections import Counter,defaultdict
from contextlib import closing
import json,math,sqlite3,statistics,sys
from pathlib import Path
from export_cheap_transfer_20260914 import DATA,FILES
from analyze_cheap_recent_transfer_20260914 import read,checked,sha,BASE
from cheap_rule_baselines_20260914 import distribution

def utility(task,score):
    if type(score) not in (float,int) or not math.isfinite(score):raise ValueError('finite grade required')
    if task=='leaf-classification':return -score
    if task=='spaceship-titanic':return score
    raise ValueError('task')

def main():
    os.umask(0o077)
    live=BASE/'forets-wallclock-20260912-km65uuej'
    sys.path[:0]=[str(live/'source/src'),str(live/'code')]
    from dojo.core.solvers.utils.response import extract_code
    from mlebench.registry import registry
    from readout_forets_generation_capacity_20260912 import numerical
    import pandas as pd
    registry=registry.set_data_dir(BASE/'mle-bench-data')
    size=read(BASE/'forets-size-only-ablation-20260914-o8h3m5qv/summary.json','67fdb9c4b3468fffb3f96e57e7374ee99c30b054e8758b4ba6b8364a7681f240')
    size_rows={(r['cohort'],r['run'],r['pool']):r for r in size['rows']}
    rows=[];denominators=[];answers={};cache={};proofs=[]
    for cohort,(suffix,hashes) in DATA.items():
        root=BASE/('forets-wallclock-20260912-'+suffix)
        s=read(root/FILES[0],hashes[0]);selected=[r for r in s['rows'] if r['technical_eligible'] and not r['duplicate_within_run']]
        both=[r for r in selected if r['labels']==[1,1]]
        denominators.append(dict(cohort=cohort,complete_pairs=len(selected),both_valid_pairs=len(both),both_valid_runs=len({r['run'] for r in both})))
        for r in both:
            cp=root/'runs'/r['run']/'checkpoint';p=cp/'forets-candidates-private'/r['pool']
            if sha(p.read_bytes())!=r['pool_sha256']:raise ValueError('pool changed')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,digest=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
            if sha(raw.encode())!=digest:raise ValueError('pool payload')
            v=json.loads(raw);nodes={n['id']:n for n in map(json.loads,checked(cp/'journal.jsonl').splitlines())}
            cfg=read(root/'configs'/(r['run']+'.json'));escrow=Path(cfg['task']['results_output_dir'])/'submission-escrow'
            if not escrow.resolve().is_relative_to(root/'runs'):raise ValueError('escrow scope')
            if str(escrow) not in cache:
                items=[]
                for complete in sorted(escrow.glob('*/complete.json')):
                    receipt=read(complete);report=read(complete.parent/'report.json',receipt['report_sha256'])
                    items.append((complete,receipt,report))
                cache[str(escrow)]=items
            scores=[];bindings=[]
            for slot,c in enumerate(v['candidates']):
                node=nodes[c['node']['id']];code=c['node']['code']
                call=next(c for c in v['task_calls'] if c['intent']['role']=='candidate' and c['slot']==slot)
                if node['code']!=code or call['state']!='returned' or sha(extract_code(code).encode())!=call['intent']['code_sha256']:raise ValueError('original code/call')
                info=node['metric_info']
                if info['valid_submission']!=1 or call['execution_metadata']['exit_code_reported']!=0:raise ValueError('original validity')
                matches=[item for item in cache[str(escrow)] if all(k in info and info[k]==value for k,value in item[2].items())]
                if len(matches)!=1:raise ValueError('original report binding not unique')
                complete,receipt,report=matches[0];submission=complete.parent/'submission.csv'
                if sha(submission.read_bytes())!=receipt['submission_sha256']:raise ValueError('submission hash')
                if r['task'] not in answers:answers[r['task']]=pd.read_csv(registry.get_competition(r['task']).answers)
                grade=numerical(r['task'],pd.read_csv(submission),answers[r['task']])
                if round(grade,5)!=report['score']:raise ValueError('independent numeric grade')
                scores.append(report['score'])
                bindings.append(dict(slot=slot,generated_code_sha256=sha(code.encode()),executed_code_sha256=call['intent']['code_sha256'],
                    report_sha256=receipt['report_sha256'],submission_sha256=receipt['submission_sha256'],complete_sha256=sha(complete.read_bytes()),
                    independent_grade=grade,binding='unique_original_journal_all_report_fields_equal_and_native_call'))
            sr=size_rows[(cohort,r['run'],r['pool'])]
            if sr['full_scores']!=r['scores']:raise ValueError('full model output')
            policies={'full':r['scores'],'uniform':[0.,0.],'short_code':r['short_scores'],'size_only':sr['size_scores']}
            utilities=[utility(r['task'],x) for x in scores]
            values={name:sum(float(p)*u for p,u in zip(distribution(pred),utilities)) for name,pred in policies.items()}
            gains={name:values['full']-values[name] for name in policies if name!='full'}
            rows.append(dict(cohort=cohort,run=r['run'],task=r['task'],pool=r['pool'],grades=scores,expected_utilities=values,
                full_minus_baseline=gains,source_pool_sha256=r['pool_sha256'],grade_bindings=bindings))
    groups=[]
    for cohort in DATA:
        for task in ('leaf-classification','spaceship-titanic'):
            rr=[r for r in rows if (r['cohort'],r['task'])==(cohort,task)]
            for name in ('uniform','short_code','size_only'):
                byrun=defaultdict(list)
                for r in rr:byrun[r['run']].append(r['full_minus_baseline'][name])
                run_values=[statistics.mean(v) for v in byrun.values()]
                groups.append(dict(cohort=cohort,task=task,baseline=name,runs=len(byrun),pairs=len(rr),
                    pair_wins=sum(r['full_minus_baseline'][name]>0 for r in rr),pair_losses=sum(r['full_minus_baseline'][name]<0 for r in rr),
                    pair_ties=sum(r['full_minus_baseline'][name]==0 for r in rr),run_equal_mean_gain=statistics.mean(run_values) if run_values else None,
                    sample_sd_run_gain=statistics.stdev(run_values) if len(run_values)>1 else None))
    result=dict(role='posthoc_initial_quality_among_both_valid_alternatives',denominators=denominators,rows=rows,groups=groups,
        script_sha256=sha(Path(__file__).read_bytes()),plan_sha256=sha(Path(__file__).with_name('CHEAP_VALID_QUALITY_DIAGNOSTIC_PLAN_20260914.md').read_bytes()),
        source_transfer_hashes={cohort:values[1][0] for cohort,values in DATA.items()},api_calls=0,gpu_jobs=0,models_fit=0,
        limitations='Very small conditional selected-source subset. Initial graded candidate utility is not eventual search utility. No score is a policy input, no current46/47 outcome access, no gate or deployment change.')
    raw=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode();path=Path(__file__).with_name('cheap-valid-quality.json')
    with path.open('xb') as f:f.write(raw)
    print(json.dumps(dict(path=str(path),sha256=sha(raw),denominators=denominators,groups=[g for g in groups if g['pairs']])))
if __name__=='__main__':main()
