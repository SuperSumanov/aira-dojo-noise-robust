"""Resolve decisions only where the exact native rule proves outcome invariance.

The original missing response stays missing. No model response/metric is imputed,
no row is dropped, and the primary incomplete readout is never overwritten.
"""
import argparse,ast,copy,hashlib,json,subprocess
from pathlib import Path
from analyze_comparison_native_selection_20260920 import summarize

COMMIT='b7f8ab0f65dba9877ac3af35e3e770fc32546565'
MCTS_SHA='f81203004ca873cc46a958a1fb9eba3b8dfabe5531f290453bcfc6f523f594d0'
PRIMARY_SHA='a202a427f512cbdfe855ee5176b58c5581d16ee2a49b2776b7579389befae000'

def proof():
    raw=subprocess.check_output(['git','show',COMMIT+':src/dojo/solvers/mcts/mcts.py'],timeout=25)
    if hashlib.sha256(raw).hexdigest()!=MCTS_SHA:raise ValueError('actual parser version')
    cls=next(n for n in ast.parse(raw).body if isinstance(n,ast.ClassDef) and n.name=='MCTS')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='parse_eval_result')
    writes=[n for n in ast.walk(method) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='is_buggy'
        and isinstance(t.value,ast.Name) and t.value.id=='node' for t in n.targets)]
    if len(writes)!=1:raise ValueError('must have exactly one buggy assignment')
    value=writes[0].value;gate=ast.parse('not node.exit_code == 0',mode='eval').body
    if not isinstance(value,ast.BoolOp) or not isinstance(value.op,ast.Or) or not any(ast.dump(term)==ast.dump(gate) for term in value.values):raise ValueError('unconditional execution-failure OR gate not proven')
    return dict(source_commit=COMMIT,source_sha256=MCTS_SHA,
        proposition='exit_code != 0 implies is_buggy=True for every possible analysis response and metric; therefore never eligible for native final choice',
        unique_assignment=True,unconditional_or_gate=True)

def resolve(rows):
    output=copy.deepcopy(rows);resolved=[];unresolved=[]
    for row in output:
        if row['analysis_status']=='returned':continue
        if type(row['exit_code']) is int and row['exit_code']!=0:
            resolved.append(dict(node=row['node'],task=row['task'],seed=row['seed'],slot=row['slot'],exit_code=row['exit_code'],
                original_analysis_status=row['analysis_status'],native_response_still_missing=True))
            # This is a decision-equivalent projection for all possible replies,
            # not a record that an analysis returned or that it predicted zero.
            row['analysis_status']='returned';row['native_accepted']=False;row['native_metric']=None
        else:unresolved.append(row['node'])
    return output,resolved,unresolved

def main(primary,reward,out):
    raw=primary.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PRIMARY_SHA:raise ValueError('original incomplete result identity')
    source=json.loads(raw);reward_raw=reward.read_bytes()
    if hashlib.sha256(reward_raw).hexdigest()!=source['reward_summary_sha256']:raise ValueError('fixed prior reward')
    certificate=proof();projected,resolved,unresolved=resolve(source['rows'])
    result=summarize(projected,json.loads(reward_raw)['encoder']['load_seconds'])
    result.update(role='closed_decision_identification_supplement_not_new_trial',primary_summary_sha256=PRIMARY_SHA,
        primary_analysis_unknown=source['unknown_count'],resolved_decisions=resolved,unresolved_decisions=unresolved,proof=certificate,
        original_rows=source['rows'],primary_status_unchanged=source['status'],new_model_calls=0,new_program_executions=0,
        additional_gpu_hours=0,source_job=source['job'],source_gpu_hours=source['gpu_hours'],
        boundary='Final choices identifiable despite one missing analysis response because execution failure independently forbids acceptance. No response imputation, retry, row deletion, or change to the primary receipt. Conditional replay remains non-E2E.')
    with out.open('x',encoding='utf-8') as file:json.dump(result,file,indent=2,allow_nan=False);file.write('\n')
    print(json.dumps(dict(status=result['status'],missing_responses=source['unknown_count'],resolved_decisions=len(resolved),unresolved_decisions=len(unresolved),
        sha256=hashlib.sha256(out.read_bytes()).hexdigest(),pools=result['pools'],aggregate=result.get('aggregate')),allow_nan=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('primary',type=Path);p.add_argument('reward',type=Path);p.add_argument('output',type=Path);a=p.parse_args();main(a.primary,a.reward,a.output)
