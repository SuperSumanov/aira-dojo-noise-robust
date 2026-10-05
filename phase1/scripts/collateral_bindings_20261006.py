"""Supplement to the same frozen sample: syntactic numeric binding changes.

No execution/dataflow equivalence claim. Name-based bindings can be unused or
shadowed. Even an actual effective change can be intentional and beneficial.
"""
import ast
import collections
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import collateral_sample_20261006 as m

KEYS = frozenset(('c alpha lr learning_rate weight_decay wd l1 l2 reg_alpha reg_lambda '
    'num_leaves max_depth min_child_samples min_child_weight subsample colsample_bytree '
    'n_estimators iterations num_boost_round num_iterations epochs num_epochs n_epochs '
    'batch_size train_batch_size eval_batch_size max_iter min_df max_df max_features '
    'ngram_range sublinear_tf lowercase norm analyzer penalty solver momentum '
    'dropout dropout_rate label_smoothing patience early_stopping_rounds '
    'n_components n_neighbors seed random_seed random_state n_splits n_folds '
    'image_size img_size input_size weight_decay_rate max_length max_len '
    'num_workers n_jobs tol tolerance').split())


class Bindings(ast.NodeVisitor):
    def __init__(self):
        self.scope = []
        self.slots = collections.defaultdict(list)

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        for a, d in zip(node.args.args[-len(node.args.defaults):], node.args.defaults):
            if a.arg.lower() in KEYS:
                self.add('default:'+a.arg, d)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def add(self, name, value):
        self.slots['/'.join(self.scope+[name])].append(m.literal(value))

    def assignment(self, target, value):
        if isinstance(target, ast.Name):
            name = target.id
        elif isinstance(target, ast.Attribute):
            name = target.attr
        else:
            return
        if name.lower() in KEYS:
            self.add('assign:'+name, value)
        if isinstance(value, ast.Dict):
            for k, v in zip(value.keys, value.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.lower() in KEYS:
                    self.add('dict:'+name+':'+k.value, v)

    def visit_Assign(self, node):
        for t in node.targets:
            self.assignment(t, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.assignment(node.target, node.value)
        self.generic_visit(node)


def extract(code):
    v = Bindings(); v.visit(ast.parse(code)); return v.slots


def compare(a,b):
    aa, bb = extract(a), extract(b)
    changes, comparable = [], 0
    for k in sorted(aa.keys() & bb.keys()):
        x,y = aa[k],bb[k]
        if len(x)==len(y)==1 and x[0] is not None and y[0] is not None:
            comparable += 1
            if x != y:
                changes.append(dict(slot=k, before=x[0]['literal'], after=y[0]['literal']))
    return dict(comparable_numeric_slots=comparable, changes=changes,
        unmatched_left_slots=len(aa.keys()-bb.keys()), unmatched_right_slots=len(bb.keys()-aa.keys()))


def tests():
    c=compare('C=30\np={"learning_rate":.1}\ndef x(batch_size=16): pass',
              'C=.1\np={"learning_rate":.2}\ndef x(batch_size=32): pass')
    assert len(c['changes'])==3
    assert not compare('C=1\nC=2', 'C=3')['changes']
    assert not compare('private_score=.3', 'private_score=.9')['changes']
    assert not compare('C=var', 'C=other')['changes']
    assert len(compare('def f():\n C=1\ndef g():\n C=2', 'def f():\n C=3\ndef g():\n C=2')['changes'])==1
    return dict(fixtures=5,status='PASS')


def main():
    os.umask(0o077)
    assert m.digest(Path(m.__file__).read_bytes())=='e5a63aafd1940b4c8e0119237a07abda7f1c3ba3bdf5f1eb3662f8ea5b272db5'
    sample_raw=(m.OUT/'sample.json').read_bytes();sample=json.loads(sample_raw)['selected']
    out=m.OUT/'binding-supplement-v1';out.mkdir(mode=0o700,exist_ok=False)
    m.save(out/'plan.json',dict(sample_sha256=m.digest(sample_raw),script_sha256=m.digest(Path(__file__).read_bytes()),
        tests=tests(), recognized_parameter_names=sorted(KEYS), max_pairs=80, generator_calls=0,model_fits=0,
        reason='Direct-constructor numeric census returned zero; inspect same frozen sample for parameter indirection, not resample.',
        boundary=__doc__))
    started=time.monotonic(); result=[]
    for filename,pin in m.PINS.items():
        raw=(m.ROOT/filename).read_bytes(); assert m.digest(raw)==pin
        source=json.loads(raw);del raw
        for r in sample:
            if r['file']!=filename:continue
            loop=source[r['task']][r['loop']];a,b=loop['base_code'],loop['code']
            assert m.digest(a)==r['base_sha256'] and m.digest(b)==r['code_sha256']
            result.append(dict(**r,**compare(a,b)))
        del source
    counts=dict(pairs=len(result), pairs_with_comparable_numeric_slots=sum(r['comparable_numeric_slots']>0 for r in result),
                numeric_binding_changed=sum(bool(r['changes']) for r in result),
                changed_tasks=len({r['task'] for r in result if r['changes']}))
    m.save(out/'summary.json',dict(counts=counts, rows=sorted(result,key=lambda r:(r['task'],r['sample_rank'])),
        elapsed_seconds=time.monotonic()-started, boundary=__doc__, outcome_accessed=False))
    print(json.dumps(dict(counts=counts, summary_sha256=m.digest((out/'summary.json').read_bytes()))))


if __name__=='__main__':
    if sys.argv[1:]==['--tests']:print(json.dumps(tests()))
    else: assert sys.argv[1:]==[]; main()
