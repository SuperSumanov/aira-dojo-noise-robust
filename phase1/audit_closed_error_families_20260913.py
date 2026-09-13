"""Descriptive error families in all saved nodes of four closed dev matrices."""
from collections import Counter
import json
from pathlib import Path
import re
from forets_environment_build_20260912 import read,write,encode,sha
from audit_recent_validation_diagnostics_20260913 import ROOTS,BASE

SECRET=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
ANSI=re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
EXCEPTION=re.compile(r'\b(TypeError|ValueError|AttributeError|KeyError|ImportError|ModuleNotFoundError|NameError|IndexError|RuntimeError|AssertionError|SyntaxError|CatBoostError|LightGBMError|XGBoostError|MemoryError|ZeroDivisionError)\s*:')
RULES={
    'fit_or_train_keyword':("got an unexpected keyword argument",),
    'early_stopping_without_validation':('For early stopping, at least one dataset and eval metric',),
    'categorical_new_fill_value':('Cannot setitem on a Categorical with a new category',),
    'unknown_target_type':("Got 'unknown' instead",'Unknown label type'),
    'missing_early_stopping_attribute':("has no attribute 'early_stopping'",),
    'feature_count_mismatch':('number of features in data','X has','Number of features of the model'),
    'missing_target_column':("KeyError: 'Transported'","KeyError: 'species'"),
    'catboost_nan_category':('cat_features must be integer or string',),
    'inconsistent_sample_counts':('inconsistent numbers of samples',),
}

def classify(term):
    if isinstance(term,list):term='\n'.join(str(s) for s in term)
    if not isinstance(term,str):raise ValueError('terminal schema')
    term=ANSI.sub('',term);matches=EXCEPTION.findall(term)
    return (matches[-1] if matches else 'no_recognized_exception',
        [k for k,terms in RULES.items() if any(t in term for t in terms)])

def main():
    rows=[];proof=[];totals=Counter();groups={}
    for name,seeds in ROOTS:
        root=BASE/name;finish=read(root/'readout-finished.json')
        if finish['status']!='verified':raise ValueError('closed historical development only')
        digest=finish.get('files',{}).get('wallclock-summary.json',finish.get('summary_sha256'))
        summary=read(root/'wallclock-summary.json',digest)
        if len(summary['rows'])!=8 or tuple(summary['seeds'])!=seeds:raise ValueError('exact complete dev matrix')
        for r in summary['rows']:
            key=(name,r['task']);group=groups.setdefault(key,Counter());group['planned_runs']+=1
            path=root/'runs'/r['run_id']/'checkpoint/journal.jsonl'
            if not path.exists():group['missing_journals']+=1;totals['missing_journals']+=1;continue
            raw=path.read_bytes();text=raw.decode();hits=len(SECRET.findall(text));text=SECRET.sub('[REDACTED]',text)
            proof.append(dict(root=name,run_id=r['run_id'],journal_sha256=sha(raw),credential_shape_redactions=hits))
            for line in text.splitlines():
                node=json.loads(line)
                if node['step']==0 or node.get('exec_time') is None:continue
                exception,patterns=classify(node.get('term_out') or '')
                failed=node.get('exit_code') not in (None,0)
                valid=(node.get('metric_info') or {}).get('valid_submission')==1
                row=dict(root=name,run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],step=node['step'],
                    exit_nonzero=failed,external_submission_valid=valid,is_buggy=node.get('is_buggy'),
                    exception_type=exception,message_families=patterns)
                rows.append(row);group['saved_executed_nodes']+=1;totals['saved_executed_nodes']+=1
                if valid:group['valid_submission_nodes']+=1;totals['valid_submission_nodes']+=1
                if failed:
                    group['nonzero_exit_nodes']+=1;totals['nonzero_exit_nodes']+=1
                    group['exception:'+exception]+=1;totals['exception:'+exception]+=1
                    for family in patterns:group['pattern:'+family]+=1;totals['pattern:'+family]+=1
                    if not patterns:group['pattern:unclassified']+=1;totals['pattern:unclassified']+=1
            if sha(path.read_bytes())!=sha(raw):raise ValueError('closed journal drift')
    result=dict(role='retrospective_observed_error_taxonomy_not_repair_efficacy',planned_runs=32,rows=rows,
        groups=[dict(root=k[0],task=k[1],counts=dict(v)) for k,v in groups.items()],totals=dict(totals),proof=proof,
        script_sha256=sha(Path(__file__).read_bytes()),
        limitations='Only saved executed nodes; missing/interrupted journals not complete coverage. Four heterogeneous protocols, correlated nodes. Message patterns can overlap; unclassified is not success. No new execution, remediation, current experiment outcomes or protected corpus.')
    raw=encode(result)
    if SECRET.search(raw.decode()):raise ValueError('unsafe public aggregate')
    target=BASE/ROOTS[-1][0]/'closed-error-families.json'
    digest=write(target,raw)
    print(json.dumps(dict(summary_sha256=digest,planned_runs=32,totals=dict(totals))))

if __name__=='__main__':main()
