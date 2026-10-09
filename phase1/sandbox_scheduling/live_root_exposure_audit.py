"""Post-result search-regime audit of all closed v7 runs; no code/value export."""
import ast
import hashlib
import json
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/scheduling-live-search-20261009-v7')
PLAN='86aa8f7a3d534ef1eaaa5475482a8838fe29c06f1ee30cb367cc05aae411c774'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())


def mechanism(source):
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MCTS')
    expand=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_expand_leaf_and_backprop')
    loop=next(n for n in expand.body if isinstance(n,ast.For))
    branch=next(n for n in loop.body if isinstance(n,ast.If))
    test=ast.unparse(branch.test)
    def calls(nodes):
        return [ast.unparse(n.func) for p in nodes for n in ast.walk(p) if isinstance(n,ast.Call)]
    then=calls(branch.body);otherwise=calls(branch.orelse)
    assignment=next(n for n in expand.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='num_children_to_create' for t in n.targets))
    setting=ast.unparse(assignment.value)
    supported=(test=='not leaf_node.parents' and 'self._draft' in then and 'self._improve' in otherwise
               and setting=='min(self.cfg.num_children, self.remaining_steps)')
    return dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        expand_ast_sha256=hashlib.sha256(ast.dump(expand,include_attributes=False).encode()).hexdigest(),
        fixed_root_draft_batch_before_next_selection=supported)


def main():
    if sha(R/'plan.json')!=PLAN or read(R/'closed.json')['complete']!=16:raise ValueError('closed v7 scope')
    source_path=R/'source/src/dojo/solvers/mcts/mcts.py'
    plan=read(R/'plan.json')
    if sha(source_path)!=plan['files'][str(source_path.relative_to(R))]:raise ValueError('native source drift')
    proof=mechanism(source_path.read_text(encoding='utf-8'))
    if not proof['fixed_root_draft_batch_before_next_selection']:raise ValueError('native mechanism changed')
    rows=[]
    for row in plan['schedule']:
        config_path=R/'configs'/f'{row["index"]}.json'
        if sha(config_path)!=plan['files'][str(config_path.relative_to(R))]:raise ValueError('config drift')
        cfg=read(config_path)['solver']
        journal=R/f'episode-{row["index"]}/checkpoint/journal.jsonl'
        nodes=[json.loads(s) for s in journal.read_text().splitlines() if s.strip()]
        kinds=[n.get('operators_used',[None])[0] if n.get('operators_used') else None for n in nodes]
        drafts=kinds.count('draft');improves=kinds.count('improve');debugs=kinds.count('debug')
        rows.append(dict(**row,config_sha256=sha(config_path),journal_sha256=sha(journal),
            num_children=cfg['num_children'],step_limit=cfg['step_limit'],time_limit_secs=cfg['time_limit_secs'],
            max_debug_depth=cfg['max_debug_depth'],max_debug_time=cfg['max_debug_time'],
            recorded_drafts=drafts,recorded_debugs=debugs,recorded_improves=improves,
            root_draft_quota_unfinished=drafts<cfg['num_children'],
            below_step_cap=(drafts+debugs+improves)<cfg['step_limit']))
    result=dict(plan_sha256=PLAN,analysis_sha256=sha(Path(__file__)),source_mechanism=proof,rows=rows,
        all_root_draft_quotas_unfinished=all(r['root_draft_quota_unfinished'] for r in rows),
        total_recorded_improves=sum(r['recorded_improves'] for r in rows),
        boundary='Post-result exposure diagnosis, not a replacement of outcome gates or proof that a different budget/policy will win. These fresh600s traces still include adaptive debug feedback, but do not establish scheduler effects on completed Improve search. Native source/control flow and final journals are used; no inference about unrecorded generation contents.')
    out=R/'root-exposure-v1.json'
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(dict(written=True,sha256=sha(out),source_mechanism=proof,
        assigned=len(rows),all_root_draft_quotas_unfinished=result['all_root_draft_quotas_unfinished'],
        total_recorded_improves=result['total_recorded_improves'],configs=[{k:r[k] for k in ('index','num_children','step_limit','time_limit_secs','recorded_drafts','recorded_debugs')} for r in rows])))


if __name__=='__main__':main()
