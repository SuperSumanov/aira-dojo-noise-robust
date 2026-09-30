"""Distinguish observed admission rejection from score-labelled critic data.

Checks an exact source route, not the membership of any historical model's
training set. Reads only missingness/boolean status from the public trace.
"""
import argparse
import ast
import collections
import hashlib
import json
import subprocess
from pathlib import Path

from check_parser_publication_0930 import SECRET, ASSIGN

REFERENCE='e385f863cb531904e611e987f7f71606796db656'
PATHS={
    'cards':'src/mle_critic/src/preprocess/download_and_resolve/cards.py',
    'builder':'src/mle_critic/src/preprocess/build_bt_pairs/build_augmented_decision_pairs.py',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expression(text):
    return ast.dump(ast.parse(text,mode='eval').body,include_attributes=False)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    def git(*items):
        return subprocess.check_output(['git','-c','safe.directory='+args.repo.resolve().as_posix(),
                                        '-C',str(args.repo),*items])
    sources={}
    trees={}
    for name,path in PATHS.items():
        raw=git('show',REFERENCE+':'+path)
        assert not SECRET.search(raw) and not ASSIGN.search(raw)
        trees[name]=ast.parse(raw)
        sources[name]={'path':path,'sha256':sha(raw),
                       'git_blob':git('rev-parse',REFERENCE+':'+path).decode().strip()}
    function=next(x for x in trees['cards'].body if isinstance(x,ast.FunctionDef) and x.name=='card_from_node_data')
    assignments={target.id:node.value for node in ast.walk(function) if isinstance(node,ast.Assign)
                 for target in node.targets if isinstance(target,ast.Name)}
    assert ast.dump(assignments['graded_score'],include_attributes=False)==expression('metric_info.get("score")')
    conditional=assignments['label']
    assert isinstance(conditional,ast.IfExp)
    assert ast.dump(conditional.test,include_attributes=False)==expression('graded_score is not None')
    assert isinstance(conditional.orelse,ast.Constant) and conditional.orelse.value is None
    function=next(x for x in trees['builder'].body if isinstance(x,ast.FunctionDef) and x.name=='build_children_index')
    loop=next(x for x in function.body if isinstance(x,ast.For))
    gate=loop.body[0]
    assert isinstance(gate,ast.If) and isinstance(gate.test,ast.BoolOp) and isinstance(gate.test.op,ast.Or)
    assert ast.dump(gate.test.values[0],include_attributes=False)==expression('card.label is None')
    assert len(gate.body)==1 and isinstance(gate.body[0],ast.Continue)
    base=args.repo/'phase1/results'
    census_path=base/'comparison_0930_parser_20261001/compiler_census.json'
    trace_path=base/'comparison_0930_feedback_diagnostic_20261001/numeric_trace.json'
    assert sha(census_path.read_bytes())=='7ba629f9dd1b4c4abc94ac4cea11c92b00c37c08e04a304551465312f72e200c'
    assert sha(trace_path.read_bytes())=='b419063798df48d75875e28c4d8f32143a851ac362f0e6cdba1715f5825ed7c8'
    census=json.loads(census_path.read_text())
    wanted={(r['run_digest'],r['segment'],r['step']) for r in census['rows'] if r['generic_feedback_exact']}
    seen=set();rows=[]
    for run in json.loads(trace_path.read_text()):
        segment=0
        for node in run['nodes']:
            if node['step']==0:
                segment+=1;continue
            key=(run['run_digest'],segment,node['step'])
            if key not in wanted:continue
            assert key not in seen;seen.add(key)
            rows.append({'run_digest':key[0],'segment':key[1],'step':key[2],
                         'score_missing':node['score'] is None,'grade_nonfinite':node['grade_nonfinite'],
                         'valid':node['valid'],'buggy':node['buggy'],
                         'exit_zero':node['exit_code']==0,'execution_zero':node['exec_seconds']==0})
    assert seen==wanted and len(rows)==204
    flags=('score_missing','grade_nonfinite','valid','buggy','exit_zero','execution_zero')
    counts={name:sum(bool(r[name]) for r in rows) for name in flags}
    assert counts=={'score_missing':204,'grade_nonfinite':0,'valid':0,'buggy':204,'exit_zero':204,'execution_zero':204}
    result={'status':'STATIC_LABEL_ROUTE_AND_PUBLISHED_TRACE_JOIN','reference_commit':REFERENCE,
            'source_files':sources,'source_route_checks':{
                'graded_score_comes_from_external_score':True,'missing_score_sets_label_none':True,
                'children_index_skips_label_none':True},'rows_checked':len(rows),'counts':counts,'rows':rows,
            'input_sha256':{'compiler_census.json':sha(census_path.read_bytes()),'numeric_trace.json':sha(trace_path.read_bytes())},
            'script_sha256':sha(Path(__file__).read_bytes()),
            'boundary':'These 204 records are missing-score observations, not demonstrated positive quality labels. This exact source rule is not a replay of all builder modes or a membership audit of any trained critic. No score value is used, no model fitted, no candidate executed.'}
    with args.output.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':main()
