"""What-if consumption plans for the bound reuse candidate. No model or pool writer."""
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import re

from phase1.historical_label_reuse_support import INPUTS, checked, check, install_guard, pairs, project
from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair, digest_records
from phase1.global_local_token_budget_plan import ARMS, build_plan
from phase1.verify_global_local_token_budget_plan import verify_arm_relations, verify_plan

ROOT = Path(__file__).resolve().parent
EXTRA = {
    'lengths': (Path('/tmp/historical-input-20260904-12Eo0Z8F/run-r2/endpoint_lengths.csv'),
                '789e87a9d6e6f44a1a526a0bb18330c425216a36f4f75341abf570dd9f11681a'),
    'old_plan': (ROOT/'results/global_local_token_plan_20260904/summary.json',
                 'c40f9b696530c2303c5129fa5571a2ffc484986472d1962871170d30a509043b'),
    'support': (ROOT/'results/historical_label_reuse_support_20260904/producer_a.json',
                '8b797c29659358473f3412b9ce5e7bd52f5af06ed756987cf31fabc7605ca21c'),
    'cost': (ROOT/'results/historical_label_reuse_cost_source_20260904/producer_a.json',
             'a03dc1206b3849f095b9fa3b41c93c238155783c4a993457c636a9e1987a2866'),
    'frozen': (ROOT/'global_local_calibration_candidate_protocol_v2.json',
               '3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9'),
    'historical': (ROOT/'global_local_historical_development_protocol_v1.json',
                   '1964e8e48e998660584c045a7e8fe2a03d61a946ba266d29d74555f934482902'),
}
CONTRACT = {
    'name': 'reuse-execution-readiness-what-if-20260904',
    'status': 'DIAGNOSTIC_ONLY_NOT_ADOPTED',
    'local_pairs': 4689, 'reuse_pairs': 3058, 'local_endpoints': 4095,
    'hypothetical_cap': 54407806, 'seeds': [6, 7, 8],
    'shapes': [[2, 8, 8], [4, 8, 4]],
    'rules': 'Use existing whole-pair stop, source-cycle boundaries and token-progress LR; do not change planner.',
    'inputs': {k: h for k, (_, h) in {**INPUTS, **EXTRA}.items()},
    'new_budget_adopted': False, 'model_fits': 0,
}


def cached_endpoints(local, rows):
    ids = sorted({v for edge in local for v in edge})
    check(len(ids) == len(rows), 'cache_coverage')
    out = {}
    for i, (cid, row) in enumerate(zip(ids, rows)):
        check(set(row) == {'ordinal', 'raw_tokens', 'valid_tokens', 'encoding_sha256'}, 'cache_schema')
        check(int(row['ordinal']) == i, 'cache_order')
        raw, valid = int(row['raw_tokens']), int(row['valid_tokens'])
        check(raw > 0 and valid == min(raw, 16384), 'cache_length')
        out[cid] = Endpoint(cid, valid, row['encoding_sha256'])
    return out


def project_reuse(local, glob, tasks):
    local_set, ids = set(local), {v for edge in local for v in edge}
    check(len(local_set) == len(local) and len(set(glob)) == len(glob), 'duplicate_pair')
    check(ids <= tasks.keys(), 'missing_local_task')
    check(all(tasks[a] == tasks[b] for a, b in local), 'local_task_mismatch')
    return tuple(e for e in glob if set(e) <= ids and e not in local_set and tasks[e[0]] == tasks[e[1]])


def plan_matrix(g, l, encoder, contract_sha, shapes, seeds):
    summaries, verifications, relations, savings = [], [], [], []
    for shape in shapes:
        for seed in seeds:
            current = {}
            for arm in ARMS:
                try:
                    plan = build_plan(arm, g, l, seed=seed, shape=shape, encoder=encoder,
                                      protocol_sha256=contract_sha)
                except ValueError as exc:
                    reason = str(exc)
                    if re.fullmatch('[a-z_]+', reason):
                        raise ValueError(f'plan_failed:{shape.world_size}:{seed}:{arm}:{reason}') from None
                    raise
                current[arm] = plan
                verifications.append(verify_plan(plan, g, l))
                item = plan.summary()
                # The reused implementation's generic status must NOT imply this successor was approved.
                item['status'] = 'HYPOTHETICAL_REUSE_PLAN_NOT_ADOPTED'
                item['world_size'] = shape.world_size
                item['segments'] = [asdict(x) for x in plan.segments]
                summaries.append(item)
            relation = verify_arm_relations(current['L1'], current['Lbudget'],
                                             current['G_to_L'], current['Ghash_to_L'])
            relation.update(seed=seed, world_size=shape.world_size)
            relations.append(relation)
            # This is token accounting only, not proof that a production checkpoint is reusable.
            independent = sum(p.planned_valid_tokens for p in current.values())
            shared = sum(p.planned_valid_tokens for a, p in current.items() if a != 'L1')
            avoided = current['L1'].planned_valid_tokens
            check(independent - shared == avoided, 'prefix_arithmetic')
            savings.append(dict(seed=seed, world_size=shape.world_size,
                five_separate_streams_valid_tokens=independent,
                four_prefix_shared_streams_valid_tokens=shared,
                hypothetical_avoided_valid_tokens=avoided,
                hypothetical_avoided_fraction=avoided/independent,
                L1_checkpoint_after_optimizer_updates=current['L1'].steps,
                evaluation_cells_kept=5, independent_streams=5, hypothetical_shared_streams=4,
                actual_model_state_equivalence_verified=False, actual_saved_GPU_hours=None))
    by = {(p['world_size'], p['seed'], p['arm']): p for p in summaries}
    for seed in seeds:
        for arm in ARMS:
            baseline = by[shapes[0].world_size, seed, arm]
            for shape in shapes[1:]:
                other = by[shape.world_size, seed, arm]
                for key in ('optimizer_steps', 'planned_pair_visits', 'planned_valid_tokens',
                            'token_budget_shortfall', 'budget_stop_next_pair_tokens', 'segments'):
                    check(baseline[key] == other[key], 'cross_shape_accounting')
    return dict(plans=summaries, independent_replays=verifications,
                cross_arm_relations=relations, hypothetical_prefix_savings=savings)


def main():
    opened = install_guard([p for p, _ in EXTRA.values()])
    bindings = {**INPUTS, **EXTRA}
    for path, sha in bindings.values(): checked(path, sha)
    local = pairs([json.loads(x) for x in INPUTS['local'][0].read_text().splitlines()])
    glob = pairs([json.loads(x) for x in INPUTS['global'][0].read_text().splitlines()])
    _, tasks = project(json.loads(INPUTS['cards'][0].read_text()))
    reuse = project_reuse(local, glob, tasks)
    with EXTRA['lengths'][0].open(newline='') as f:
        endpoints = cached_endpoints(local, list(csv.DictReader(f)))
    check((len(local), len(reuse), len(endpoints)) == (4689, 3058, 4095), 'fixed_counts_drift')
    old = json.loads(EXTRA['old_plan'][0].read_text())['input_bindings']
    support = json.loads(EXTRA['support'][0].read_text())['metrics']
    cost = json.loads(EXTRA['cost'][0].read_text())
    check(support['reusable_global_pairs'] == len(reuse), 'support_binding')
    check(cost['new_gpu_jobs'] == cost['model_fits'] == 0 and not cost['pool_written'], 'cost_scope')
    for a, b in [('local_train_sha256', 'local'), ('global_source_sha256', 'global'), ('grouped_cards_sha256', 'cards')]:
        check(old[a] == INPUTS[b][1], 'old_encoding_input_binding')
    encoder = EncoderBinding(old['tokenizer_binding_sha256'], old['serialization_binding_sha256'], 16384)
    def describe(source, edges):
        return tuple(Pair.canonical(source, endpoints[a], endpoints[b],
            digest_records([(encoder.serialization_sha256, tasks[a])])) for a, b in edges)
    g, l = describe('G', reuse), describe('L', local)
    cap = sum(x.valid_tokens for x in g+l)
    check(cap == CONTRACT['hypothetical_cap'] == cost['cached_input_cost']['hypothetical_reuse_then_local_tokens'], 'cap_binding')
    contract_sha = digest_records([CONTRACT])
    result = plan_matrix(g, l, encoder, contract_sha,
                         [BatchShape(*s) for s in CONTRACT['shapes']], CONTRACT['seeds'])
    for path, sha in bindings.values(): checked(path, sha, scan=False)
    return dict(status='REUSE_EXECUTION_PLANS_VERIFIED_EFFECT_BLOCKED',
        contract=CONTRACT, contract_sha256=contract_sha, **result,
        data_open_counts=dict(opened), source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        tokenizer_reruns=0, model_weights_loaded=0, model_fits=0, new_gpu_jobs=0, api_calls=0,
        new_budget_adopted=False, pool_written=False, protected_cohort_files_opened=0,
        source_gate_passed=False, production_training_integration_verified=False)


if __name__ == '__main__':
    try: print(json.dumps(main(), sort_keys=True, allow_nan=False))
    except Exception as exc:
        reason = str(exc)
        print(json.dumps(dict(status='FAILED_CLOSED', exception_type=type(exc).__name__,
            safe_reason=reason if re.fullmatch('[A-Za-z0-9_:]+', reason) else 'details_withheld')))
        raise SystemExit(1)
