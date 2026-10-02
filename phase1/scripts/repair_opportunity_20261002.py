"""Frozen retrospective upper-bound diagnostic on closed development runs only.

Prediction swapping is an ORACLE diagnostic, not a deployed policy. No fitting,
candidate code execution, LLM calls or test-set access. The length groups were
defined in the original protocol from public training inputs.
"""
import csv
import hashlib
import importlib.util
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
OLD = B / 'task-feedback-real-20261001-v6'
CENSUS = B / 'edit-factorization-census-20261002-v1'
ROOT = B / 'repair-opportunity-20261002-v1'
COMMIT = 'df7dc14eb2103558708574ae3373b9123cd8b3c4'
SUMMARY_SHA = '3de13b0b85d25da6f68b941a0d2e2db142754200aa6b525edde3c5579e21e582'
TASKS = ('spooky-author-identification', 'random-acts-of-pizza', 'tweet-sentiment-extraction')
KEYS = dict(zip(TASKS, ('id', 'request_id', 'textID')))
METRICS = dict(zip(TASKS, ('log_loss', 'auc', 'mean_word_jaccard')))


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def save(p, obj):
    with p.open('x') as f: json.dump(obj, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n')
def stats(values):
    return dict(n=len(values), median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values) > 1 else None)


def auto(row):
    return row['batch'] == OLD.name or (row['batch'] == 'task-feedback-upper-20261002-v1' and row['arm'] in ('A', 'B'))


def main():
    os.umask(0o077); started = time.monotonic(); ROOT.mkdir()
    assert sha(CENSUS / 'summary.json') == SUMMARY_SHA
    census = read(CENSUS / 'summary.json')
    verification = read(CENSUS / 'verification.json')
    assert verification['summary_sha256'] == SUMMARY_SHA and verification['parent_bindings'] == 85
    assert sha(OLD / 'task_feedback_real_20261001.py') == '4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
    plan = dict(question='Is there room beyond the strongest historical prediction after removing manual-guidance examples?',
                role='RETROSPECTIVE_ORACLE_UPPER_BOUND_NOT_METHOD_EFFECT', source_sha256=sha(Path(__file__)), source_commit=COMMIT,
                census_sha256=SUMMARY_SHA, denominator=len(census['rows']), group_family='original public-training word-count tertiles; exactly3',
                interventions='replace parent predictions with child predictions only within one predefined group; 3 choices',
                primary_subset='all original ABC and upper A/B; exclude upper C and local F/P manual guidance',
                comparison='actual parent; full child; strongest valid historical program across ALL actions in 3 closed roots, with frozen neutral rule on Tweet',
                metrics='native overall trusted D_search plus independent metric; within-group and cross-boundary AUC decomposition',
                ties_epsilon=1e-12, no_effect_based_exclusion=True, cost='no new GPU/API/fits; inherited generation/training costs not zero',
                leakage='D_search reused and already viewed; no training or deployable selector; every oracle result is optimistic',
                protected_opened=False, invocation=sys.argv, python=sys.version.split()[0])
    save(ROOT / 'plan.json', plan)
    sys.path.insert(0, str(OLD)); import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from task_feedback_facts_20261001 import groups, aggregate
    import sklearn
    from sklearn.metrics import roc_auc_score
    rule = B / 'task-feedback-public-rule-20261002-v1/rule.json'
    assert sha(rule) == '2beaad25ab591c957f1183de5b17457ff738b25130d13075df500c36bb4fbfc0'
    assert read(rule)['chosen'] == dict(column='sentiment', value='neutral', operation='copy_full_text')
    task_data = {}; cache = {}; bindings = {}; references = {}
    roots = read(CENSUS / 'plan.json')['roots']
    # Configs/data paths are taken from the exact completed plans, not a search
    # over unrelated datasets. Bind all score inputs and all source predictions.
    for task in TASKS:
        config = next(s['index'] for s in read(OLD / 'plan.json')['schedule'] if s['task'] == task)
        obj = MLEBenchTask(RunConfig.load_from_json(OLD / 'configs' / f'{config}.json').task)
        assert obj._search_only_score is not None and not obj.private_dir.exists()
        spec = obj._search_only_module.SPEC[task]
        labels = B / spec.get('source', spec.get('view')) / 'private/dsearch.csv'
        truth = rows(labels); cuts, bins = groups(task, obj.public_dir); key = KEYS[task]
        assert len(truth) == len(bins) and {r[key] for r in truth} == set(bins)
        public = None
        if task == TASKS[2]:
            public = {r[key]: r for r in rows(obj.public_dir / 'test.csv')}
        task_data[task] = obj, truth, bins, cuts, public
        bindings[str(labels)] = sha(labels)
        for p in obj.public_dir.iterdir():
            if p.name in ('train.csv', 'test.csv', 'train.json', 'test.json'): bindings[str(p)] = sha(p)

    def utility(task, truth, pred):
        if not truth: return None
        if task == TASKS[1]:
            y = [int(r['requester_received_pizza']) for r in truth]
            if len(set(y)) != 2: return None
            return float(roc_auc_score(y, [float(r['requester_received_pizza']) for r in pred]))
        value = aggregate(task, truth, pred)
        return -value if task == TASKS[0] else value

    def load_prediction(task, action):
        if str(action) in cache: return cache[str(action)]
        meta = read(action / 'result.json')
        if not meta['valid']: cache[str(action)] = None; return None
        p = action / 'submission.private.csv'; bindings[str(p)] = sha(p)
        obj, truth, bins, cuts, public = task_data[task]; key = KEYS[task]
        data = rows(p); by_id = {r[key]: r for r in data}
        assert len(data) == len(by_id) == len(truth) and set(by_id) == set(bins)
        pred = [by_id[r[key]] for r in truth]
        receipt = obj._search_only_score(task, p)
        assert receipt['split'] == 'D_search_development_only'
        sign = -1 if task == TASKS[0] else 1
        u = utility(task, truth, pred)
        assert math.isclose(u, sign * receipt[METRICS[task]], abs_tol=1e-11)
        assert math.isclose(u, sign * float(meta['metric']), abs_tol=1e-11)
        # Existing frozen, task-specific baseline is applied uniformly to both
        # parent and child. Otherwise old neutral-copy gains masquerade as new.
        if task == TASKS[2]:
            pred = [dict(r, selected_text=public[r[key]]['text']) if public[r[key]]['sentiment'] == 'neutral' else r for r in pred]
            u = utility(task, truth, pred)
        cache[str(action)] = (pred, u)
        return pred, u

    for basename, expected in roots.items():
        root = B / basename
        assert sha(root / 'plan.json') == expected and (root / 'all-closed.json').is_file()
        for s in read(root / 'plan.json')['schedule']:
            for a in sorted((root / f'episode-{s["index"]}').glob('action-*')):
                if not (a / 'result.json').is_file(): continue
                loaded = load_prediction(s['task'], a)
                if loaded is None: continue
                if s['task'] not in references or loaded[1] > references[s['task']]['utility']:
                    references[s['task']] = dict(utility=loaded[1], prediction_sha256=sha(a / 'submission.private.csv'), origin=str(a))

    output = []; groups_out = []
    for index, r in enumerate(census['rows']):
        task = r['task']; ep = B / r['batch'] / f'episode-{r["episode"]}'
        parent = load_prediction(task, ep / f'action-{r["parent_step"]}')
        child = load_prediction(task, ep / f'action-{r["step"]}')
        assert parent is not None
        info = dict(index=index, task=task, batch=r['batch'], episode=r['episode'], step=r['step'], parent_step=r['parent_step'],
                    arm=r['arm'], generation_seed=r['generation_seed'], source_commit=COMMIT, plan_sha256=sha(ROOT / 'plan.json'),
                    automatic_guidance=auto(r), parent_code_sha256=r['parent_raw_sha256'], child_code_sha256=r['child_raw_sha256'],
                    child_valid=child is not None, parent_utility=parent[1], child_utility=child[1] if child else None,
                    strongest_historical_utility=references[task]['utility'])
        if child is None: output.append(info); continue
        obj, truth, bins, cuts, public = task_data[task]; key = KEYS[task]
        swaps = []
        for group in range(3):
            mask = [bins[t[key]] == group for t in truth]
            subgroup = [t for t, m in zip(truth, mask) if m]
            pp = [p for p, m in zip(parent[0], mask) if m]
            cp = [p for p, m in zip(child[0], mask) if m]
            within0, within1 = utility(task, subgroup, pp), utility(task, subgroup, cp)
            new = [c if m else p for p, c, m in zip(parent[0], child[0], mask)]
            u = utility(task, truth, new); gain = u - parent[1]
            weight = len(subgroup) / len(truth)
            if task == TASKS[1]:
                pos = sum(int(t['requester_received_pizza']) for t in truth); neg = len(truth) - pos
                gp = sum(int(t['requester_received_pizza']) for t in subgroup); gn = len(subgroup) - gp
                weight = gp * gn / (pos * neg)
            local_delta = within1 - within0 if within0 is not None and within1 is not None else None
            within_contribution = 0. if weight == 0 else weight * local_delta
            external = gain - within_contribution
            if task != TASKS[1]: assert abs(external) < 1e-11
            row = dict(index=index, task=task, automatic_guidance=auto(r), group=group, n=len(subgroup),
                       local_delta=local_delta, weighted_local_contribution=within_contribution, cross_boundary_contribution=external,
                       swap_global_gain=gain, swap_utility=u,
                       local_global_sign_reversal=(local_delta is not None and local_delta * gain < -1e-18),
                       beyond_strong_reference=u - references[task]['utility'])
            groups_out.append(row); swaps.append(u)
        info.update(best_group_swap_utility=max(swaps), best_group_swap_gain=max(swaps)-parent[1],
                    oracle_beyond_both_endpoints=max(swaps)-max(parent[1],child[1]),
                    oracle_beyond_strong_reference=max(swaps)-references[task]['utility'])
        output.append(info)
    summaries = {}
    for task in TASKS:
        for scope in ('all', 'automatic'):
            subset = [r for r in output if r['task'] == task and (scope == 'all' or r['automatic_guidance'])]
            valid = [r for r in subset if r['child_valid']]
            subset_groups = [r for r in groups_out if r['task'] == task and (scope == 'all' or r['automatic_guidance'])]
            summaries[task + ':' + scope] = dict(proposals=len(subset), valid=len(valid),
                unique_parents=len({r['parent_code_sha256'] for r in subset}),
                full_child_worse=sum(r['child_utility'] < r['parent_utility']-1e-12 for r in valid),
                rescue_worse_child=sum(r['child_utility'] < r['parent_utility']-1e-12 and r['best_group_swap_gain'] > 1e-12 for r in valid),
                swap_exceeds_endpoints=sum(r['oracle_beyond_both_endpoints'] > 1e-12 for r in valid),
                swap_exceeds_strong_reference=sum(r['oracle_beyond_strong_reference'] > 1e-12 for r in valid),
                local_global_sign_reversals=sum(r['local_global_sign_reversal'] for r in subset_groups),
                oracle_gain_statistics=stats([r['best_group_swap_gain'] for r in valid]),
                oracle_vs_strong_statistics=stats([r['oracle_beyond_strong_reference'] for r in valid]))
    for name, data in (('pairs.csv',output),('groups.csv',groups_out)):
        fields = list(dict.fromkeys(k for r in data for k in r))
        with (ROOT/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    save(ROOT/'bindings.private.json',bindings)
    result = dict(status='DESCRIPTIVE_ORACLE_ONLY', plan_sha256=sha(ROOT/'plan.json'), denominator=len(output),
                  summaries=summaries, references=references, elapsed_seconds=time.monotonic()-started,
                  score_files=len(cache), valid_score_files=sum(v is not None for v in cache.values()),
                  gpu=0, api_calls=0, fits=0, protected_opened=False, sklearn=sklearn.__version__,
                  outputs={n:sha(ROOT/n) for n in ('pairs.csv','groups.csv','bindings.private.json')},
                  interpretation='Posthoc upper bounds; repeated related programs and reused development labels. Not E2E, novel rules, independent generalization, matched budget, or a usable selection algorithm.')
    save(ROOT/'summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('references','outputs')},sort_keys=True))


if __name__ == '__main__': main()
