"""Independent scope/gate/accounting check; no experiment or model rerun."""
import ast,csv,hashlib,json,math,os,statistics,subprocess,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/natural-opportunity-20261003-v1')
PLAN='39948b4a517cdb609105f099231bb9c3d1c19214754d585a6365245635b903df'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(code):return ast.dump(ast.parse(code),include_attributes=False)
def table(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def close(a,b):return a is None and b is None or a is not None and b is not None and math.isclose(a,b,abs_tol=1e-11,rel_tol=1e-11)

def structural():
    assert sha(R/'plan.json')==PLAN;p=read(R/'plan.json');intake=read(R/'intake.json')
    assert sum(s['available'] for s in intake['states'])==5 and len(intake['states'])==6
    for f,h in p['files'].items():assert sha(R/f)==h
    for state in (0,1,3,4,5):
        original=(R/'starts'/f'{state}.py').read_text()
        for seed in (42,173):
            ss={s['arm']:s for s in p['schedule'] if s['state']==state and s['seed']==seed}
            assert set(ss)=={'original','modified'}
            codes={arm:(R/'programs'/f'{s["index"]}.private.py').read_text() for arm,s in ss.items()}
            # Reverse only the preregistered intervention, independently from builder.
            patch=codes['modified']
            if state==0:
                before='test_prob_final = [test_prob_word, test_prob_char, test_prob_combined][int(np.argmin([np.mean(cv_scores_word), np.mean(cv_scores_char), np.mean(cv_scores_combined)]))]'
                after='test_prob_final = 0.4 * test_prob_combined + 0.3 * test_prob_word + 0.3 * test_prob_char'
            elif state==1:before="    p.update(objective='binary', metric='auc')\n";after=''
            elif state==3:
                before="    from sklearn.pipeline import FeatureUnion\n    tfidf = FeatureUnion([('char', tfidf), ('word', TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=100000, sublinear_tf=True))])\n";after=''
            elif state==4:before='xgb.XGBClassifier(**xgb_params, early_stopping_rounds=50)';after='xgb.XGBClassifier(**xgb_params)'
            else:before='np.triu(np.ones((tl, tl), dtype=bool))';after='np.tril(np.ones((tl, tl), dtype=bool))'
            assert patch.count(before)==1,(state,'anchor');patch=patch.replace(before,after)
            assert tree(patch)==tree(codes['original']),(state,'extra intervention')
            for arm,s in ss.items():
                cfg=read(R/'configs'/f'{s["index"]}.json');assert cfg['metadata']['seed']==seed
                assert cfg['interpreter']['env']['PYTHONHASHSEED']==str(seed)
                for n in ast.walk(ast.parse(codes[arm])):
                    if isinstance(n,ast.keyword) and n.arg=='random_state' and isinstance(n.value,ast.Constant):assert n.value.value==seed
                    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SEED' for t in n.targets):assert n.value.value==seed
    return p

def verify():
    p=structural();s=read(R/'readout.json');rr=table(R/'readout-runs.csv');pp=table(R/'readout-pairs.csv')
    assert len(rr)==20 and len(pp)==10 and len({(r['state'],r['seed'],r['arm']) for r in rr})==20
    job=read(R/'launch.json')['job'];bindings=[]
    for row in p['schedule']:
        ep=R/f'episode-{row["index"]}';n=read(ep/'native.json');a=ep/'action-0'
        assert n['job']==job and len(n['gpu_uuids'])==1 and n['config_sha256']==sha(R/'configs'/f'{row["index"]}.json')
        b=read(a/'binding.json');assert b['system_bindpaths_disabled'] and b['namespace']['exact_device_namespace']
        bindings.append(sha(a/'binding.json'))
        result=read(a/'result.json');assert result['seconds']<450 and read(ep/'closed.json')['returncode']==0
    # Algebra/gates from exported run rows, independent of analysis helper.
    expected=[]
    for state in (0,1,3,4,5):
        vals=[];task=None
        for seed in (42,173):
            d={r['arm']:r for r in rr if int(r['state'])==state and int(r['seed'])==seed};a=d['original'];b=d['modified'];task=a['task']
            v=(float(b['score'])-float(a['score']))*(-1 if task.startswith('spooky') else 1) if a['valid']==b['valid']=='True' else None
            pair=next(r for r in pp if int(r['state'])==state and int(r['seed'])==seed)
            assert close(v,float(pair['oriented_gain']) if pair['oriented_gain'] else None);vals.append(v)
        threshold=.01 if task.startswith('tweet') else .005;ok=all(v is not None and v>=threshold for v in vals)
        known=[v for v in vals if v is not None];row=next(r for r in s['states'] if r['state']==state)
        assert row['qualifies']==ok and close(row['median_gain'],statistics.median(known) if known else None)
        assert close(row['sample_variance'],statistics.variance(known) if len(known)>1 else None)
        expected.append(dict(state=state,task=task,qualified=ok))
    qualified=sorted({r['task'] for r in expected if r['qualified']});assert qualified==s['qualified_tasks'] and s['cross_task_gate']==(len(qualified)>=2)
    for path,h in read(R/'readout-bindings.private.json').items():assert sha(Path(path))==h
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    text=subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=25)
    line=next(x for x in text.splitlines() if x.split('|')[0]==job);fields=line.split('|');assert fields[1]=='COMPLETED' and fields[4]=='0:0'
    tres=dict(x.split('=',1) for x in fields[3].split(',') if '=' in x);gpus=int(tres['gres/gpu']);elapsed=int(fields[2]);assert gpus==2 and elapsed<=5400
    out=dict(status='PASS',utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),plan_sha256=PLAN,
        summary_sha256=sha(R/'readout.json'),verifier_sha256=sha(Path(__file__)),isolated_executions=len(bindings),
        modifications_verified=10,states=expected,cross_task_gate=len(qualified)>=2,job=job,job_state=fields[1],elapsed_seconds=elapsed,
        allocated_gpus=gpus,allocated_gpu_hours=elapsed*gpus/3600,binding_hashes=bindings,
        boundary='Checks patch scope, explicit seeds, GPU namespace, paired arithmetic, output immutability and allocated cost. Score algebra was independently checked in the frozen readout. Not new-task generalization or automatic method success.')
    with (R/'verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k!='binding_hashes'}))
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='structural':structural();print('STRUCTURAL_PASS')
    else:verify()
