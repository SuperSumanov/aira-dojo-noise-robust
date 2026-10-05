"""Posthoc outcome-blind coverage census, not a regression/prevalence estimator.

Do not replace the original 80-pair sample, reselect cases, execute downloaded
code, or inspect public outcome/feedback/scenario values. Categories are names
and declared imports, not execution semantics or physical-run independence.
"""
import argparse
import ast
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import time

import collateral_sample_20261006 as m
import collateral_bindings_20261006 as binding

OUT=Path('/research/d7/spc/yzyang4/collateral-population-20261006-v1')
FRAMEWORKS=frozenset('torch torchvision transformers timm tensorflow sklearn xgboost lightgbm catboost'.split())
SEED_NAMES=frozenset('seed random_seed random_state'.split())
EXEC_NAMES=frozenset('num_workers n_jobs'.split())
SPLIT_NAMES=frozenset('n_splits n_folds'.split())
CAP_NAMES=frozenset('epochs num_epochs n_epochs batch_size train_batch_size eval_batch_size max_iter n_estimators iterations num_boost_round num_iterations max_features max_length max_len image_size img_size input_size n_components'.split())


def category(name):
    name=name.lower()
    for names,label in ((SEED_NAMES,'seed_like'),(EXEC_NAMES,'execution_parallelism_like'),(SPLIT_NAMES,'split_count_like'),(CAP_NAMES,'capacity_or_training_effort_like')):
        if name in names:return label
    return 'other_supported_setting'


def imports(tree):
    names=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):names.update(x.name.split('.')[0] for x in n.names)
        elif isinstance(n,ast.ImportFrom) and n.module:names.add(n.module.split('.')[0])
    return names & FRAMEWORKS


def tests():
    assert category('LR')=='other_supported_setting' and category('N_JOBS')=='execution_parallelism_like'
    assert imports(ast.parse('import torch as t\nfrom sklearn.linear_model import X'))=={'torch','sklearn'}
    assert m.tests()['forbidden_field_sentinel']=='PASS' and binding.tests()['status']=='PASS'
    print('POPULATION_CENSUS_TESTS_PASS')


def main(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit)
    tests();os.umask(0o077)
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('census cap')));signal.alarm(600)
    OUT.mkdir(mode=0o700,exist_ok=False)
    m.save(OUT/'plan.json',dict(source_commit=commit,script_sha256=m.digest(Path(__file__).read_bytes()),source_pins=m.PINS,
        helper_sha256={Path(x.__file__).name:m.digest(Path(x.__file__).read_bytes()) for x in (m,binding)},
        question='What structural population did the small executable text-task check cover?',
        selection='Every unique (task, exact base code, exact child code) in the three already pinned public traces; no outcome-based selection.',
        categories='Name-based, potentially unused/shadowed settings. Imports are declarations, not executed model identity. Different ASTs are not independent runs.',
        no_outcome_fields=True,no_code_execution=True,no_model_fits=True,gpu_hours=0,api_calls=0,max_seconds=600,
        old_sample_unchanged=True,automatic_expansion=False,limitations=__doc__))
    started=time.monotonic();seen=set();parents=set();parent_pairs=collections.Counter();tasks=collections.defaultdict(collections.Counter)
    counts=collections.Counter();categories=collections.Counter();frameworks=collections.Counter();parameter_names=collections.Counter();unsupported=collections.Counter()
    for filename,pin in m.PINS.items():
        raw=(m.ROOT/filename).read_bytes();assert m.digest(raw)==pin
        record=json.loads((m.ROOT/(filename+'.download.json')).read_text());assert record['sha256']==pin and not record['credential_categories']
        source=json.loads(raw);del raw
        for row,a,b in m.permitted_pairs(source,filename):
            counts['raw_pairs']+=1;key=(row['task'],row['base_sha256'],row['code_sha256'])
            if key in seen:counts['exact_duplicate_pairs']+=1;continue
            seen.add(key);counts['unique_pairs']+=1;tc=tasks[row['task']];tc['unique_pairs']+=1
            try:
                at,bt=ast.parse(a),ast.parse(b)
                direct=m.inspect_pair(a,b);bound=binding.compare(a,b)
                assert direct['parse']=='PASS'
            except (SyntaxError,ValueError,RecursionError) as exc:
                counts['unparsed_or_unsupported']+=1;tc['unparsed_or_unsupported']+=1;unsupported[type(exc).__name__]+=1;continue
            counts['parsed_pairs']+=1;tc['parsed_pairs']+=1
            parent=(row['task'],m.digest(ast.dump(at,include_attributes=False)));parents.add(parent);parent_pairs[parent]+=1
            if direct['eligible_unique_common_classes']:counts['direct_comparable_pairs']+=1;tc['direct_comparable_pairs']+=1
            if bound['comparable_numeric_slots']:counts['binding_comparable_pairs']+=1;tc['binding_comparable_pairs']+=1
            if direct['numeric_changes']:counts['direct_changed_pairs']+=1;tc['direct_changed_pairs']+=1
            if bound['changes']:counts['binding_changed_pairs']+=1;tc['binding_changed_pairs']+=1
            names={x['parameter'].lower() for x in direct['numeric_changes']}|{x['slot'].split(':')[-1].lower() for x in bound['changes']}
            declared=imports(at)|imports(bt)
            if names:
                counts['any_supported_change_pairs']+=1;tc['any_supported_change_pairs']+=1
                for name in names:parameter_names[name]+=1
                for cat in {category(n) for n in names}:categories[cat]+=1
                for framework in declared:frameworks[framework]+=1
                if 'torch' in declared or 'tensorflow' in declared:counts['changed_pairs_declaring_neural_framework']+=1;tc['changed_pairs_declaring_neural_framework']+=1
                if names <= SEED_NAMES|EXEC_NAMES|SPLIT_NAMES:counts['only_seed_execution_or_split_names_changed']+=1
        del source
    for task,c in tasks.items():c['distinct_parent_asts']=sum(t==task for t,h in parents)
    counts['tasks']=len(tasks);counts['distinct_parent_asts']=len(parents)
    counts['max_pairs_sharing_parent_ast']=max(parent_pairs.values(),default=0)
    result=dict(counts=dict(counts),per_task={k:dict(v) for k,v in sorted(tasks.items())},
        changed_pair_name_categories=dict(categories),changed_pair_declared_frameworks=dict(frameworks),
        changed_parameter_pair_counts=dict(parameter_names),unsupported=dict(unsupported),
        elapsed_seconds=time.monotonic()-started,plan_sha256=m.digest((OUT/'plan.json').read_bytes()),
        no_outcome_fields=True,no_candidate_identity_export=True,no_method_claim=True,old_sample_unchanged=True,
        limitation='A structural census with limited detector support. Not rates of harmful, unintended, executed, recoverable or beneficial edits. No physical-run or causal independence claim.')
    m.save(OUT/'summary.json',result)
    print(json.dumps(dict(counts=result['counts'],categories=result['changed_pair_name_categories'],frameworks=result['changed_pair_declared_frameworks'],elapsed_seconds=result['elapsed_seconds'],summary_sha256=m.digest((OUT/'summary.json').read_bytes()))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit');p.add_argument('--tests',action='store_true');a=p.parse_args()
    if a.tests:tests()
    else:main(a.commit)
