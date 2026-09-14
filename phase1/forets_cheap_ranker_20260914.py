"""Frozen local code-only selector. No task identity, labels or network input."""
import ast,hashlib,json,math,time,warnings
from collections import Counter
from pathlib import Path

AST_TYPES=('Import','ImportFrom','Call','FunctionDef','ClassDef','For','While','If','Try','With','Assign','Subscript','Attribute','ListComp','DictComp','Lambda','Return','Raise','ExceptHandler','Constant','Name','Compare','BinOp','BoolOp')
FEATURE_NAMES=('log_chars','log_lines','syntax_invalid','max_ast_depth')+tuple('log_'+n for n in AST_TYPES)
MODEL_SHA='05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1'
MODEL_PATH='/research/d7/spc/yzyang4/forets-task-validity-20260914-n8q3h72y/code_only.private.joblib'
def features(code):
    code=code[:30000];counts=Counter();invalid=0;depth=0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',SyntaxWarning);tree=ast.parse(code)
        stack=[(tree,0)]
        while stack:
            node,level=stack.pop();counts[type(node).__name__]+=1;depth=max(depth,level)
            stack.extend((child,level+1) for child in ast.iter_child_nodes(node))
    except SyntaxError:invalid=1
    return [math.log1p(len(code)),math.log1p(code.count('\n')+1),invalid,depth]+[math.log1p(counts[n]) for n in AST_TYPES]
def rank_codes(solver,codes,root,step):
    kind=solver.cfg.cheap_ranker
    if kind not in ('short_code','learned_validity') or not codes or not all(isinstance(c,str) for c in codes):raise ValueError('explicit cheap ranker/code pool')
    started=time.monotonic();init=0.
    if kind=='short_code':scores=[float(-len(c[:30000])) for c in codes]
    else:
        if not hasattr(solver,'_cheap_model'):
            import joblib,sklearn
            raw=Path(MODEL_PATH).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=MODEL_SHA or sklearn.__version__!='1.6.1':raise ValueError('frozen model/runtime drift')
            import io
            artifact=joblib.load(io.BytesIO(raw))
            if artifact['condition']!='code_only' or tuple(artifact['features'])!=FEATURE_NAMES:raise ValueError('model feature contract')
            solver._cheap_model=artifact['model'];init=time.monotonic()-started
        scores=[float(v) for v in solver._cheap_model.predict_proba([features(c) for c in codes])[:,1]]
    if len(scores)!=len(codes) or any(not math.isfinite(v) for v in scores):raise ValueError('complete finite score vector')
    path=Path(root)/'forets-cheap-ranker-private';path.mkdir(exist_ok=True)
    receipt=dict(kind=kind,step=step,codes_sha256=[hashlib.sha256(c.encode()).hexdigest() for c in codes],scores=scores,
        model_sha256=MODEL_SHA if kind=='learned_validity' else None,init_seconds=init,query_seconds=time.monotonic()-started-init)
    with (path/f'batch-{step}.json').open('x') as f:json.dump(receipt,f,sort_keys=True,allow_nan=False)
    return scores
