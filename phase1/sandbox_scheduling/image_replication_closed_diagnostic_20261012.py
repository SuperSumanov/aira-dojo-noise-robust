"""Post-closure receipt alignment only; no rescoring, new endpoint, or experiment."""
import ast,hashlib,json,math
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/scheduling-image-deadline-replication-20261012-v1')
PIN='23f368399f6c735ef81142ec46831ae4e9f45d58d80edf5d2559b4cbb7a22ea6'

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finite(x):return type(x) in (int,float) and math.isfinite(x)

def main():
    assert sha(R/'plan.json')==PIN
    closed=read(R/'completion-closed.json')
    assert closed['summary_sha256']==sha(R/'readout-v1/summary.json')
    p=read(R/'plan.json');rows=[]
    for name in ('source/src/dojo/solvers/mcts/mcts.py','source/src/dojo/core/solvers/utils/journal.py','runtime.py'):
        assert sha(R/name)==p['files'][name]
    for a in p['schedule']:
        ep=R/f"episode-{a['index']}";f=read(ep/'finished.json');cfg=read(R/f"configs/{a['index']}.json")
        path=ep/'checkpoint/journal.jsonl'
        nodes=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        good=[n for n in nodes if not n.get('is_buggy') and finite(n.get('metric'))]
        best=(min if a['task']=='denoising-dirty-documents' else max)([n['metric'] for n in good],default=None)
        assert f['native_selected_valid']==bool(good) and f['native_selected_score']==best
        candidates=[read(q) for q in sorted(ep.glob('candidate-*.json')) if '.private.' not in q.name]
        exports=[]
        for c in candidates:
            if not c['valid']:continue
            matched=[n for n in nodes if hashlib.sha256((n.get('code') or '').encode()).hexdigest()==c['code_sha256']]
            exports.append(dict(elapsed=c['elapsed_seconds'],score=c['score'],exit_code=c['exit_code'],timed_out=c['timed_out'],journal_matches=len(matched),
                matched_good=sum(not n.get('is_buggy') and finite(n.get('metric')) for n in matched),
                matched_state=[{k:n.get(k) for k in ('is_buggy','metric','exit_code')} for n in matched]))
        events=[json.loads(x) for x in (ep/'events.jsonl').read_text().splitlines() if x.strip()]
        tail=[{k:e[k] for k in ('event','call','elapsed','seconds','success') if k in e}
            for e in events if e['event'] in ('generation_started','generation_returned')][-6:]
        training=[read(q) for q in ep.glob('gpu-training-*.json') if 'missing' not in q.name]
        rows.append(dict(index=a['index'],arm=a['arm'],task=a['task'],status=f['status'],finish_elapsed=f['elapsed_seconds'],
            use_test_score=cfg['solver'].get('use_test_score'),candidates=len(candidates),valid=sum(c['valid'] for c in candidates),nonzero=sum(c['exit_code']!=0 for c in candidates),
            timed_out=sum(c['timed_out'] for c in candidates),execution_seconds=sum(c['exec_seconds'] for c in candidates),
            candidate_queue_seconds=sum(e.get('wait_seconds',0) for e in events if e['event'] in ('admitted','admission_interrupted') and e.get('kind')=='candidate'),
            journal_nodes=len(nodes),good_nodes=len(good),valid_candidate_alignment=exports,
            generation_tail=tail if exports and not good else [],
            cuda_gradient_steps=[t.get('cuda_gradient_steps') for t in training]))
    source=(R/'source/src/dojo/solvers/mcts/mcts.py').read_text();tree=ast.parse(source)
    conditions=[n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='is_buggy' for t in n.targets)]
    llm_veto=any(isinstance(n,ast.Subscript) and isinstance(n.slice,ast.Constant) and n.slice.value=='is_bug' for c in conditions for n in ast.walk(c))
    print(json.dumps(dict(plan_sha256=PIN,summary_sha256=closed['summary_sha256'],journal_selection_checks=len(rows),
        buggy_condition_reads_llm_is_bug=llm_veto,external_metric_override_present='response["metric"] = float(eval_result[VALIDATION_FITNESS])' in source,
        source_sha256={n:sha(R/n) for n in ('source/src/dojo/solvers/mcts/mcts.py','source/src/dojo/core/solvers/utils/journal.py','runtime.py')},
        rows=rows,limitation='Post-hoc descriptive alignment; native endpoints and frozen false quality gate unchanged. No raw code, output text, prediction values, labels, or credentials exported.'),allow_nan=False))

if __name__=='__main__':main()
