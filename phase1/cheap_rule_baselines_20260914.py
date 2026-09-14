"""No-fit strong rules plus independent incomplete-pool/model verification."""
import os
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='1'
from contextlib import closing
from collections import Counter,defaultdict
import ast,importlib.util,itertools,json,sqlite3,sys,warnings
from pathlib import Path
import numpy as np,joblib
from analyze_cheap_recent_transfer_20260914 import read,checked,sha,BASE
SOURCES={
 'scope':('88v5m9dr','9938703b5f96b98f142114bee71d6d58431558cefc8af96b7f4443829ef2d51c'),
 'action':('7wzrny21','f66697e7e22e252a605d2ee195eafaa1986a424f0bc2d127d7ccfbabc310d68c'),
 'width':('2z2s7sc3','00b7bd5c28b48d15bc34311f348fb035b4c81eb96f359e051cda5bcbd256bb0c'),
 'memory':('103zf3nb','d2fe3fb28ec5306b1a95058a5f88e9625382043b9a4478ae04f762c00462cbec')}
def distribution(values):
    top=max(values);mask=np.array([x==top for x in values],dtype=float);return mask/mask.sum()
def interval(a,b,ys):
    d=distribution(a)-distribution(b)
    values=[float(np.dot(d,full)) for full in itertools.product(*[((0,1) if y is None else (y,)) for y in ys])]
    return min(values),max(values)
def rules(codes):
    syntax=[];lengths=[];lines=[]
    for full in codes:
        code=full[:30000];lengths.append(-len(code));lines.append(-(code.count('\n')+1))
        try:
            with warnings.catch_warnings():warnings.simplefilter('ignore',SyntaxWarning);ast.parse(code)
            syntax.append(1)
        except SyntaxError:syntax.append(0)
    return dict(short_code=lengths,fewer_lines=lines,syntax_only=syntax,syntax_then_short=list(zip(syntax,lengths)))
def main(cohort):
    os.umask(0o077);suffix,digest=SOURCES[cohort];root=BASE/('forets-wallclock-20260912-'+suffix)
    result=read(root/'cheap-transfer-missingness.json',digest);live=BASE/'forets-wallclock-20260912-km65uuej'
    source=live/'source/src/dojo/solvers/fore_ts/cheap_ranker.py';inv=read(live/'source-files.json')
    if sha(source.read_bytes())!=inv['src/dojo/solvers/fore_ts/cheap_ranker.py']:raise ValueError('deployed source hash')
    spec=importlib.util.spec_from_file_location('production_features',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if sha(Path(module.MODEL_PATH).read_bytes())!=result['model_sha256']:raise ValueError('model drift')
    model=joblib.load(module.MODEL_PATH)['model'];cache={};rows=[];syntax_counts=Counter()
    sys.path.insert(0,str(root/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    for row in result['rows']:
        cp=root/'runs'/row['run']/'checkpoint';p=cp/'forets-candidates-private'/row['pool']
        if sha(p.read_bytes())!=row['pool_sha256']:raise ValueError('pool hash')
        with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
        if sha(raw.encode())!=h:raise ValueError('pool payload')
        v=json.loads(raw);codes=[c['node']['code'] for c in v['candidates']]
        if row['run'] not in cache:
            jp=cp/'journal.jsonl';cache[row['run']]={n['id']:n for n in (json.loads(line) for line in checked(jp).splitlines())} if jp.exists() else {}
        ys=[]
        for slot,candidate in enumerate(v['candidates']):
            calls=[c for c in v['task_calls'] if c['slot']==slot and c['intent']['role']=='candidate']
            if len(calls)>1:raise ValueError('duplicate original execution')
            n=cache[row['run']].get(candidate['node']['id'])
            if not calls or calls[0]['state']!='returned' or n is None:ys.append(None);continue
            if codes[slot]!=n['code'] or sha(extract_code(codes[slot]).encode())!=calls[0]['intent']['code_sha256']:raise ValueError('original code binding')
            if calls[0]['execution_metadata']['exit_code_reported']!=n.get('exit_code'):raise ValueError('exit metadata')
            ec=n.get('exit_code');flag=(n.get('metric_info') or {}).get('valid_submission',n.get('metric_info/valid_submission'))
            ys.append(None if ec is None else 0 if ec!=0 else None if flag is None else int(flag is True or flag==1))
        hs=model.predict_proba(np.asarray([module.features(c) for c in codes]))[:,1].tolist()
        if hs!=row['hgb_scores'] or ys!=row['labels']:raise ValueError('independent model/raw labels')
        rs=rules(codes)
        if rs['short_code']!=row['short_scores']:raise ValueError('code-size binding')
        if interval(hs,rs['short_code'],ys)!=(row['gain_lower'],row['gain_upper']):raise ValueError('independent sharp bound')
        syntax_counts.update(rs['syntax_only']);out=dict(run=row['run'],task=row['task'],technical_eligible=row['technical_eligible'],pool=row['pool'],
            duplicate_within_run=row['duplicate_within_run'],fully_known=row['fully_known'],original_complete_case=row['from_original_complete_case'],labels=ys,
            hgb_validity=float(np.dot(distribution(hs),ys)) if row['fully_known'] else None,comparators={})
        for name,values in rs.items():
            lo,hi=interval(hs,values,ys)
            out['comparators'][name]=dict(gain_lower=lo,gain_upper=hi,validity=float(np.dot(distribution(values),ys)) if row['fully_known'] else None)
        rows.append(out)
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        rr=[r for r in rows if r['task']==task and r['technical_eligible'] and not r['duplicate_within_run']]
        for name in ('short_code','fewer_lines','syntax_only','syntax_then_short'):
            perrun=defaultdict(list)
            for r in rr:perrun[r['run']].append(r['comparators'][name])
            known=[r for r in rr if r['fully_known']];critical=[r for r in known if r['labels'][0]!=r['labels'][1]]
            groups.append(dict(task=task,baseline=name,runs=len(perrun),all_applicable_pairs=len(rr),fully_known_pairs=len(known),known_discordant=len(critical),
                hgb_valid_on_discordant=sum(r['hgb_validity'] for r in critical),baseline_valid_on_discordant=sum(r['comparators'][name]['validity'] for r in critical),
                run_equal_lower=float(np.mean([np.mean([x['gain_lower'] for x in v]) for v in perrun.values()])) if perrun else None,
                run_equal_upper=float(np.mean([np.mean([x['gain_upper'] for x in v]) for v in perrun.values()])) if perrun else None))
    output=dict(role='no_fit_rules_and_independent_missingness_verification',cohort=cohort,source_missingness_sha256=digest,
        source_model_sha256=result['model_sha256'],rows=rows,groups=groups,syntax_prefix_parse_counts=dict(syntax_counts),
        script_sha256=sha(Path(__file__).read_bytes()),plan_sha256=sha(Path(__file__).with_name('CHEAP_RULE_BASELINES_PLAN_20260914.md').read_bytes()),
        independently_verified_all_included_model_predictions_labels_and_bounds=True,api_calls=0,gpu_jobs=0,models_refit=0,
        limits='Post-hoc fixed rule stress tests; uncertainty bounds are not confidence intervals, source-selection and workspace caveats persist. No current E2E gate or method changed.')
    raw=(json.dumps(output,sort_keys=True,allow_nan=False)+'\n').encode()
    with (root/'cheap-rule-baselines.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),cohort=cohort,groups=groups,syntax_counts=dict(syntax_counts))))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('cohort',choices=tuple(SOURCES));main(p.parse_args().cohort)
