"""Supplementary closed-only cost/recipe facts; never replaces frozen primary.

Written before seeing v2 effects. No raw code, prompts, predictions or labels leave
the development root. Syntax summaries do not certify semantic equivalence.
"""
import ast, collections, hashlib, json
from pathlib import Path
from implementation_reset_v2_20261005 import R, check, read, write, sha, schedule

CLASSES={'TfidfVectorizer','CountVectorizer','LogisticRegression','LogisticRegressionCV',
         'MultinomialNB','ComplementNB','BernoulliNB','SVC','LinearSVC','CalibratedClassifierCV',
         'XGBClassifier','LGBMClassifier','RandomForestClassifier','CatBoostClassifier','Pipeline'}
KEYS={'C','alpha','analyzer','ngram_range','min_df','max_df','max_features','sublinear_tf',
      'solver','penalty','max_iter','random_state','n_estimators','num_leaves','norm','stop_words'}
WORDS={'word','char','char_wb','lbfgs','liblinear','sag','saga','newton-cg','newton-cholesky',
       'l1','l2','elasticnet','english','none'}

def recipe(code):
    tree=ast.parse(code);aliases={};constructors=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            for a in n.names:aliases[a.asname or a.name.split('.')[0]]=a.name.split('.')[-1]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call):continue
        name=getattr(n.func,'id',getattr(n.func,'attr',''));name=aliases.get(name,name)
        if name not in CLASSES:continue
        params={}
        for k in n.keywords:
            if k.arg not in KEYS:continue
            try:v=ast.literal_eval(k.value)
            except (ValueError,TypeError):v='DYNAMIC'
            if isinstance(v,(int,float,bool)) or v is None:params[k.arg]=v
            elif isinstance(v,tuple) and all(isinstance(x,int) for x in v):params[k.arg]=list(v)
            elif isinstance(v,str) and v in WORDS:params[k.arg]=v
            else:params[k.arg]='DYNAMIC_OR_OTHER'
        constructors.append(dict(name=name,parameters=params))
    return dict(constructors=constructors,semantic_verified=False,
                limitation='Literal constructor summary only; dataflow, actual fitted objects and preprocessing may differ.')

def main():
    check();assert (R/'closed.json').exists() and read(R/'closed.json')['service_closed']
    assert (R/'readout-v1/summary.json').exists(),'primary readout first'
    rows=[]
    for s in schedule():
        ep=R/f"episode-{s['index']}";actions=[];generation_seconds=0;execution_seconds=0
        for ap in sorted(ep.glob('action-*'),key=lambda p:int(p.name.split('-')[1])):
            if (ap/'generation.private.json').exists():generation_seconds+=read(ap/'generation.private.json')['generation_seconds']
            if (ap/'result.json').exists():execution_seconds+=read(ap/'result.json')['exec_seconds']
            if not (ap/'code.private.json').exists():continue
            code=read(ap/'code.private.json')['code']
            a=dict(action=ap.name,code_sha256=hashlib.sha256(code.encode()).hexdigest(),recipe=recipe(code),
                   executed=(ap/'result.json').exists(),rejected=(ap/'contract-rejection.json').exists())
            if (ap/'submission.private.csv').exists():a['prediction_sha256']=sha(ap/'submission.private.csv')
            actions.append(a)
        finished=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        rows.append(dict(**s,elapsed_seconds=finished.get('elapsed_seconds'),returned_generation_seconds=generation_seconds,
                         recorded_execution_seconds=execution_seconds,actions=actions,
                         unique_code_hashes=len({a['code_sha256'] for a in actions}),
                         unique_prediction_hashes=len({a['prediction_sha256'] for a in actions if 'prediction_sha256' in a})))
    report=dict(scope='Post-closure descriptive mechanism/cost supplement; no change to frozen effects or gate',rows=rows,
                warning='Generation sums exclude timed-out unreturned calls; execution sums exclude unfinished attempts. Whole deadline/allocation receipts are authoritative costs. Constructor counts are not fitted-model counts.')
    write(R/'readout-v1/mechanism-cost.json',report)
    print(json.dumps({'rows':len(rows),'path':str(R/'readout-v1/mechanism-cost.json'),'sha256':sha(R/'readout-v1/mechanism-cost.json')}))

if __name__=='__main__':main()
