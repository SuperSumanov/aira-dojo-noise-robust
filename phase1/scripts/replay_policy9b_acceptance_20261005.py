"""Posthoc CPU replay of closed observations, NOT a counterfactual rollout.

Compare native parsing with only the learned is_bug veto removed for externally
valid, successful executions. Preserve every other gate and the primary result.
No generated program or model runs; no predictions/labels exported or reread.
"""
import argparse, ast, copy, hashlib, json, logging, math, os, sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

R=Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')
PARSER_SHA='f75a93f69fd79029ae4d3ce5b9dad81520480cbf36b56b05d8719a8b84c2a63d'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def qualified(c):
    return c['valid'] is True and c['exit_code']==0 and not c['timed_out'] and type(c['score']) in (int,float) and math.isfinite(c['score'])
def intervention(response,c):
    r=copy.deepcopy(response)
    if qualified(c):r['is_bug']=False
    return r

def main():
    assert read(R/'readout-v1/summary.json')['status']=='CLOSED_DEVELOPMENT_QUALIFICATION'
    assert sha(R/'source/src/dojo/solvers/mcts/mcts.py')==PARSER_SHA
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',HF_HUB_OFFLINE='1',
        LOGGING_DIR=str(R),SUPERIMAGE_DIR=str(R/'no-image'),MLE_BENCH_DATA_DIR=str(R/'no-official-data'))
    sys.path.insert(0,str(R/'source/src'))
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.solvers.utils.journal import Node
    from dojo.core.interpreters.base import ExecutionResult
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,AUX_EVAL_INFO
    # Do not instantiate the solver or any model. The original method sees a stub
    # whose _analyze returns the already-recorded response, without network access.
    def replay(response,c,lower):
        n=Node(code='closed-observation-only')
        stub=SimpleNamespace(logger=logging.getLogger('closed-replay'),cfg=SimpleNamespace(use_test_score=False),
            lower_is_better=lower,_analyze=lambda _:copy.deepcopy(response))
        result={EXECUTION_OUTPUT:ExecutionResult(term_out=[],exec_time=c.get('exec_seconds',0),exit_code=c['exit_code'],timed_out=c['timed_out']),
            VALID_SOLUTION:c['valid'],VALIDATION_FITNESS:c['score'],AUX_EVAL_INFO:copy.deepcopy(c.get('aux') or {})}
        MCTS.parse_eval_result(stub,n,result)
        return dict(buggy=bool(n.is_buggy),score=None if n.is_buggy else n.metric.value)
    controls=[]
    good=dict(valid=True,exit_code=0,timed_out=False,score=.7)
    for field,value in [('valid',False),('exit_code',1),('score',None),('timed_out',True)]:
        c=dict(good,**{field:value});response={'is_bug':True,'metric':None,'summary':''}
        assert intervention(response,c)==response
        assert replay(intervention(response,c),c,False)['buggy']
        controls.append(field)
    rows=[];evidence={}
    for s in read(R/'plan.json')['schedule']:
        ep=R/f"episode-{s['index']}";jp=ep/'checkpoint/journal.jsonl';evidence[str(jp.relative_to(R))]=sha(jp)
        cs={}
        for p in ep.glob('candidate-*.json'):
            if p.name.endswith('.private.json'):continue
            c=read(p);assert c['code_sha256'] not in cs,'ambiguous candidate join'
            cs[c['code_sha256']]=(p.name,c);evidence[str(p.relative_to(R))]=sha(p)
        for n in (json.loads(x) for x in jp.read_bytes().splitlines() if x):
            if not n.get('operators_used'):continue
            key=hashlib.sha256(n['code'].encode()).hexdigest();name,c=cs.pop(key)
            responses=[m['completion_text'] for role,m in zip(n['operators_used'],n['operators_metrics']) if role=='analysis']
            assert len(responses)==1
            response=responses[0]
            if isinstance(response,str):
                try:response=json.loads(response)
                except json.JSONDecodeError:response=ast.literal_eval(response)
            assert isinstance(response,dict) and type(response['is_bug']) is bool
            original=replay(response,c,s['task']=='spooky-author-identification')
            assert original['buggy']==n['is_buggy']
            if not original['buggy']:assert abs(original['score']-n['metric'])<=1e-12
            altered=replay(intervention(response,c),c,s['task']=='spooky-author-identification')
            # Independent logical calculation, not a second call to native parser.
            expected_original=response['is_bug'] or c['exit_code']!=0 or c['score'] is None or not c['valid']
            assert original['buggy']==expected_original
            assert altered['buggy']==(False if qualified(c) else expected_original)
            rows.append(dict(**s,candidate=name,operator=n['operators_used'][0],externally_valid=qualified(c),
                analysis_is_bug=response['is_bug'],native=original,veto_only_replay=altered,
                code_sha256=key,elapsed_seconds=c['elapsed_seconds']))
        assert not cs,'candidate missing from closed journal'
    counts=dict(completed_candidates=len(rows),native_reproduced=len(rows),
        independent_logic_checks=len(rows),externally_valid=sum(x['externally_valid'] for x in rows),
        native_accepted=sum(not x['native']['buggy'] for x in rows),
        veto_only_replay_accepted=sum(not x['veto_only_replay']['buggy'] for x in rows),
        valid_vetoed=sum(x['externally_valid'] and x['native']['buggy'] for x in rows),
        affected_runs=len({x['index'] for x in rows if x['externally_valid'] and x['native']['buggy']}))
    report=dict(status='POSTHOC_FIXED_OBSERVATION_REPLAY',parser_sha256=PARSER_SHA,
        script_sha256=sha(Path(__file__)),primary_summary_sha256=sha(R/'readout-v1/summary.json'),
        primary_gate_unchanged=True,counts=counts,negative_controls=controls,rows=rows,evidence_sha256=evidence,
        scope='Observed candidate acceptance only. The intervention would change the subsequent path, so replayed later candidates and endpoint are not a counterfactual rollout. External validity is not a universal semantic or anti-cheating proof. One affected development run, not independent cross-task replication. No model benefit or novel algorithm claimed.')
    path=R/'acceptance-replay-v1.json'
    with path.open('x') as f:json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(status=report['status'],counts=counts,negative_controls=controls,sha256=sha(path))))

if __name__=='__main__':main()
