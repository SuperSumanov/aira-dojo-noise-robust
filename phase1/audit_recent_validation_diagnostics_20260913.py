"""All saved journals of four explicitly closed dev matrices; no protected corpus."""
import ast
from collections import Counter
import json
from pathlib import Path
from forets_environment_build_20260912 import read,write,encode,sha

BASE=Path('/research/d7/spc/yzyang4')
ROOTS=[('forets-wallclock-20260912-bll4ghfa',(26,27)),('forets-wallclock-20260912-2o9mw39n',(28,29)),
       ('forets-wallclock-20260912-y_p2tlmi',(30,31)),('forets-wallclock-20260912-5_czzimk',(32,33))]
BASELINES={'bdac82a587f1c3ca1fa70cbc701f7f753823b367fddb7a53e5b578126fa42e6f',
           '6610c17e158b33592ce355f460761826cc30cf05c1fd0099e75ba4ac7b0022c9'}


def suspicious_concatenation(code):
    tree=ast.parse(code)
    extended={n.func.value.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
              and n.func.attr=='extend' and isinstance(n.func.value,ast.Name)}
    scoring=any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='accuracy_score'
                and len(n.args)>1 and isinstance(n.args[1],ast.Name) and n.args[1].id in extended for n in ast.walk(tree))
    split=any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='split' for n in ast.walk(tree))
    return scoring and split  # A review candidate, never a proof of an indexing bug.


def main():
    rows=[];cases=[];proof=[];totals=Counter()
    for name,seeds in ROOTS:
        root=BASE/name;finish=read(root/'readout-finished.json')
        if finish['status']!='verified':raise ValueError('unclosed source')
        h=finish.get('files',{}).get('wallclock-summary.json',finish.get('summary_sha256'))
        summary=read(root/'wallclock-summary.json',h)
        if len(summary['rows'])!=8 or tuple(summary['seeds'])!=seeds:raise ValueError('exact eight registered dev runs')
        proof.append(dict(root=name,finish_sha256=sha((root/'readout-finished.json').read_bytes()),summary_sha256=h))
        for r in summary['rows']:
            cp=root/'runs'/r['run_id']/'checkpoint/journal.jsonl';counts=Counter()
            if cp.exists():
                raw=cp.read_bytes()
                for line in raw.splitlines():
                    node=json.loads(line)
                    if node['step']==0 or node.get('exec_time') is None:continue
                    counts['saved_executed_nodes']+=1
                    info=node.get('metric_info') or {};valid=info.get('valid_submission')==1
                    codehash=sha(node['code'].encode());baseline=codehash in BASELINES
                    if valid:
                        counts['valid_submissions']+=1
                        if not baseline:counts['valid_nonbaseline_submissions']+=1
                    mismatch=valid and node.get('exit_code')==0 and node.get('is_buggy') is True
                    pattern=suspicious_concatenation(node['code'])
                    if mismatch:counts['valid_exit_zero_marked_buggy']+=1
                    if pattern:counts['syntactic_concatenation_review_candidates']+=1
                    if mismatch or pattern:
                        cases.append(dict(root=name,run_id=r['run_id'],step=node['step'],code_sha256=codehash,
                            valid_exit_zero_marked_buggy=mismatch,search_metric_missing=node.get('metric') is None,
                            concatenation_pattern_needs_review=pattern,external_valid=valid))
                journal_hash=sha(raw)
                if sha(cp.read_bytes())!=journal_hash:raise ValueError('journal mutation')
            else:counts['journal_missing']=1;journal_hash=None
            rows.append(dict(root=name,run_id=r['run_id'],technical_eligible=r['technical_eligible'],journal_sha256=journal_hash,counts=dict(counts)))
            totals.update(counts)
    out=dict(role='retrospective_saved_journal_incidence_not_e2e_or_score_channel_effect',runs=len(rows),totals=dict(totals),rows=rows,cases=cases,proof=proof,
        script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Four heterogeneous development protocols, not iid confirmation. Missing/partial journals cannot reveal every action. Syntactic patterns require manual semantic review; valid-submission/bug disagreement can be justified by missing validation, not necessarily a false alarm.')
    path=BASE/ROOTS[-1][0]/'recent-validation-diagnostic-incidence.json'
    print(json.dumps(dict(sha256=write(path,encode(out)),runs=len(rows),totals=dict(totals),cases=cases)))


if __name__=='__main__':main()
