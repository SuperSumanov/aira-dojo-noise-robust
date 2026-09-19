"""Cross-check acceptance using the actual pinned MCTS parser body.

Only closed safe summaries are read. The response is already a dictionary, so
the JSON text parser is an identity; task transport and metrics are test doubles.
This checks native acceptance semantics, not an end-to-end search effect.
"""
import argparse,ast,copy,hashlib,json,re,subprocess
from pathlib import Path
from types import SimpleNamespace as NS

COMMIT='be9335348b569086ef9b0af36a15b13e61fec45c'
SOURCE='src/dojo/solvers/mcts/mcts.py'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})')

def native_parser():
    raw=subprocess.check_output(['git','show',COMMIT+':'+SOURCE],timeout=30)
    if SECRET.search(raw):raise ValueError('source credential scan')
    tree=ast.parse(raw);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MCTS')
    method=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='parse_eval_result'))
    method.returns=None
    for arg in method.args.args:arg.annotation=None
    namespace=dict(parse_json_output=lambda value:value,
        MetricValue=lambda value,**kwargs:NS(value=value),WorstMetricValue=lambda **kwargs:NS(value=None))
    for key in ('EXECUTION_OUTPUT','VALID_SOLUTION_FEEDBACK','VALIDATION_FITNESS','AUX_EVAL_INFO','VALID_SOLUTION'):
        namespace[key]=key
    module=ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[]))
    exec(compile(module,COMMIT+':'+SOURCE,'exec'),namespace)
    return namespace['parse_eval_result'],hashlib.sha256(raw).hexdigest()

def decide(parser,*,is_bug,metric,exit_code,valid_guard):
    node=NS(id='verification-only',exit_code=exit_code,_term_out=[])
    node.absorb_exec_result=lambda result:None
    response=dict(is_bug=is_bug,metric=metric,summary='')
    logger=NS(debug=lambda *_:None,error=lambda *_:None,warning=lambda *_:None,info=lambda *_:None)
    solver=NS(cfg=NS(use_test_score=False),lower_is_better=True,logger=logger,_analyze=lambda _:copy.deepcopy(response))
    feedback={'EXECUTION_OUTPUT':None}
    if valid_guard is not None:feedback['VALID_SOLUTION']=valid_guard
    parser(solver,node,feedback)
    return not node.is_buggy

def verify(summary,banks,parser):
    if summary['role']!='native_cache_acceptance_component_not_e2e' or summary['planned']!=8:raise ValueError('scope')
    if [row['request_seed'] for row in summary['rows']]!=list(range(801,809)):raise ValueError('matrix')
    verified=[];unknown=[]
    for row in summary['rows']:
        source,=[candidate for candidate in banks[row['seed']]['rows'] if candidate['run']==row['run'] and candidate['node']==row['node']]
        if source['code_sha256']!=row['code_sha256'] or source['valid'] is not row['official_valid']:raise ValueError('source identity')
        if row['native_acceptance'] is None:unknown.append(row['index']);continue
        # Actual cases have no timeout. Do not silently equate a different
        # future timeout convention with the original parser semantics.
        if source['timed_out']:raise ValueError('timeout requires separate native semantics review')
        values=dict(is_bug=row['native_is_bug'],metric=row['native_metric'],exit_code=source['exit_code'])
        raw=decide(parser,**values,valid_guard=None)
        guarded=decide(parser,**values,valid_guard=source['valid'])
        if raw is not row['native_acceptance'] or guarded is not row['accepted_with_external_validity_guard']:
            raise ValueError('native production parser disagrees')
        verified.append(row['index'])
    return dict(status='PASS_NATIVE_PARSER_COMPONENT_ONLY',verified_indices=verified,unknown_indices=unknown,
                no_external_metric_used=True,full_search_executed=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);p.add_argument('bank1',type=Path);p.add_argument('bank2',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    raw=args.summary.read_bytes();summary=json.loads(raw);banks={};hashes={}
    for seed,path in ((1,args.bank1),(2,args.bank2)):
        data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
        if digest!=summary['source_summary_sha256'][str(seed)]:raise ValueError('bank digest')
        banks[seed]=json.loads(data);hashes[str(seed)]=digest
    parser,digest=native_parser();result=verify(summary,banks,parser)
    result.update(source_commit=COMMIT,source_path=SOURCE,source_sha256=digest,summary_sha256=hashlib.sha256(raw).hexdigest(),bank_sha256=hashes)
    with args.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result,indent=2))
