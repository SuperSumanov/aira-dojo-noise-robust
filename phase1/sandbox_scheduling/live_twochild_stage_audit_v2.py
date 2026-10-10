"""Post-close diagnostic correction: distinguish the explicit virtual root.

The original diagnostic refused the root's empty operator list before writing.
Retain that refusal; this separate output changes no primary/secondary gate.
"""
import ast
import json
from pathlib import Path
from lifecycle_pilot import read, sha, write
import live_twochild_stage_audit as original


def prove_root(source):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MCTS')
    fn = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='create_root_node')
    call = fn.body[0].value
    if not isinstance(call,ast.Call) or ast.unparse(call.func) != 'MCTSNode':
        raise ValueError('unsupported root constructor')
    kwargs = {k.arg:ast.literal_eval(k.value) for k in call.keywords if k.arg in ('code','plan','analysis','is_buggy')}
    calls = [ast.unparse(n) for n in ast.walk(fn) if isinstance(n,ast.Call)]
    if kwargs != dict(code='',plan='',analysis='',is_buggy=True) or 'self.journal.append(self.root_node)' not in calls:
        raise ValueError('root construction changed')
    return True


def counts(nodes, children):
    roots=[]; candidates=[]
    for node in nodes:
        root=(node.get('operators_used')==[] and type(node.get('step')) is int
              and node['step']==0 and node.get('parents')==[] and node.get('is_buggy') is True
              and all(node.get(k)=='' for k in ('code','plan','analysis')))
        (roots if root else candidates).append(node)
    if len(roots)!=1:
        raise ValueError('exactly one source-grounded virtual root required')
    result=original.counts(candidates,children)
    result.update(virtual_root_records=len(roots),journal_records=len(nodes))
    return result


def main():
    root=original.ROOT
    if sha(root/'plan.json')!=original.PLAN or not (root/'closed.json').exists():
        raise ValueError('exact closed trial required')
    primary=root/'readout-v1/summary.json'
    if read(primary)['plan_sha256']!=original.PLAN: raise ValueError('primary first')
    plan=read(root/'plan.json')
    if sorted(r['index'] for r in plan['schedule'])!=list(range(16)): raise ValueError('all16')
    source=root/'source/src/dojo/solvers/mcts/mcts.py'
    if sha(source)!=plan['files'][str(source.relative_to(root))]: raise ValueError('source drift')
    native=source.read_text(encoding='utf-8'); prove_root(native)
    proof=original.mechanism(native)
    if not proof['fixed_root_draft_batch_before_next_selection']: raise ValueError('root mechanism')
    rows=[]
    for assignment in plan['schedule']:
        config=root/'configs'/f'{assignment["index"]}.json'
        if sha(config)!=plan['files'][str(config.relative_to(root))]: raise ValueError('config drift')
        cfg=read(config)['solver']
        if cfg['num_children']!=2 or cfg['time_limit_secs']!=1500: raise ValueError('common baseline')
        journal=root/f'episode-{assignment["index"]}/checkpoint/journal.jsonl'
        row=dict(**assignment,journal_observed=journal.exists(),config_sha256=sha(config))
        if journal.exists():
            nodes=[json.loads(s) for s in journal.read_text().splitlines() if s.strip()]
            row.update(counts(nodes,2),journal_sha256=sha(journal))
        rows.append(row)
    result=dict(plan_sha256=original.PLAN,primary_sha256=sha(primary),analysis_sha256=sha(__file__),
        original_analysis_sha256=sha(original.__file__),source_mechanism=proof,assigned=16,rows=rows,
        correction='Original v1 refused the explicit virtual root before writing. Only the unique step0/parentless/empty-code-plan-analysis/buggy/empty-operator root is separated; other unknown operators still fail closed.',
        changes_primary_gate=False,
        boundary='Post-result stage diagnosis, not a positive outcome test. Recorded Improve is not score improvement; missing/unrecorded work is not inferred.')
    out=root/'stage-coverage-v2.json'; write(out,result)
    print(json.dumps(dict(written=True,sha256=sha(out),assigned=16,
        observed_journals=sum(r['journal_observed'] for r in rows),
        recorded_improves=sum(r.get('recorded_improves',0) for r in rows)),sort_keys=True))


if __name__=='__main__': main()
