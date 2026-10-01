"""Posthoc source comparison on all three completed Pizza F revisions.

No code execution, model fit, hidden data or new effect. This is NOT proof of
causal mediation: code preservation is checked separately from observed quality.
"""
import argparse,ast,copy,hashlib,json,re,sys
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-local-edit-20261002-v1')
PLAN='7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def read(p):return json.loads(p.read_bytes())
def dump(n):return ast.dump(n,include_attributes=False)
def function(tree,name):
    z=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name];assert len(z)==1
    return copy.deepcopy(z[0])
def feature_contract(tree):
    fn=function(tree,'build_features');target=[]
    for n in ast.walk(fn):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Constant) and t.slice.value=='days_since_start' for t in n.targets):target.append(n)
    assert len(target)==1
    expr=target[0].value
    expected_old=ast.parse('(ts-ts.min()).dt.days',mode='eval').body
    expected_global=ast.parse('(ts-ORIGIN).dt.days',mode='eval').body
    expected_arg=ast.parse('(ts-origin).dt.days',mode='eval').body
    kind='batch_min' if dump(expr)==dump(expected_old) else ('fixed_global' if dump(expr)==dump(expected_global) else ('fixed_argument' if dump(expr)==dump(expected_arg) else 'unrecognized'))
    target[0].value=ast.Constant(value='TARGET_EXPRESSION_REMOVED')
    fn.body=[n for n in fn.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
    fn.args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='df')],kwonlyargs=[],kw_defaults=[],defaults=[])
    return kind,dump(fn)
def vectorizer(tree):
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='TfidfVectorizer'];assert len(calls)==1
    return {k.arg:ast.literal_eval(k.value) for k in calls[0].keywords}
def run():
    assert hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest()==PLAN and (ROOT/'all-closed.json').exists()
    sys.path.insert(0,str(ROOT));from task_feedback_real_20261001 import m
    p=m.check();m.setup();from dojo.utils.code_parsing import extract_code
    rows=[]
    for s in p['schedule']:
        if s['arm']!='F' or s['task']!='random-acts-of-pizza':continue
        ep=ROOT/f'episode-{s["index"]}';codes=[]
        for step in (0,1):
            raw=(ep/f'action-{step}/node.private.json').read_bytes();assert not SECRET.search(raw),'credential withheld'
            codes.append(extract_code(json.loads(raw)['code']))
        old,new=map(ast.parse,codes);a,b=feature_contract(old),feature_contract(new)
        ov,nv=vectorizer(old),vectorizer(new)
        result=read(ep/'action-1/result.json');initial=read(ep/'action-0/result.json')
        rows.append(dict(index=s['index'],seed=s['seed'],code_sha256=[hashlib.sha256(c.encode()).hexdigest() for c in codes],
            parent_feature_rule=a[0],revised_feature_rule=b[0],other_feature_function_ast_equal=a[1]==b[1],
            text_feature_helper_ast_equal=dump(function(old,'text_feats'))==dump(function(new,'text_feats')),
            vectorizer_changes={k:{'parent':ov.get(k),'revised':nv.get(k)} for k in sorted(set(ov)|set(nv)) if ov.get(k)!=nv.get(k)},
            initial=initial['metric'],revised=result['metric'],saved=result['selected_metric'],
            revised_minus_initial=result['metric']-initial['metric']))
    assert len(rows)==3 and all(r['other_feature_function_ast_equal'] and r['text_feature_helper_ast_equal'] for r in rows)
    return dict(scope='posthoc all three Pizza F revisions; AST evidence of unchanged numeric feature body apart from target rule, and changed TFIDF parameters. No new execution; not a formal proof of whole-program equivalence or causal attribution of score loss.',plan_sha256=PLAN,rows=rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run()
    with a.out.open('x') as f:json.dump(r,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(r,sort_keys=True))
