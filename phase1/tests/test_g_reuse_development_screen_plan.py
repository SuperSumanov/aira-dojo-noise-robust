from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from phase1.g_reuse_development_screen_plan import MATRIX, prepare_screen, preparation_summary
from phase1.global_local_execution_plan import EncoderBinding, PlanError
from phase1.global_local_training_inputs import prepare_training_inputs
from phase1.verify_global_local_token_budget_plan import verify_plan


ROOT = Path(__file__).resolve().parents[1]


class Tokenizer:
    def __call__(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return {'input_ids': [1 + ord(c) % 127 for c in text]}


def fixture():
    cards = [{'endpoint_id': f'card{i}', 'task_name': 'synthetic-task', 'code': f'x={i}\n'} for i in range(8)]
    g = [('card0', 'card2'), ('card1', 'card3'), ('card4', 'card6'), ('card5', 'card7')]
    l = [('card0', 'card1'), ('card2', 'card3'), ('card4', 'card5'), ('card6', 'card7')]
    return cards, g, l


def prepared(args=None, max_len=16384):
    protocol = (ROOT/'g_reuse_development_screen_v1.json').read_bytes()
    return prepare_training_inputs(*(fixture() if args is None else args), Tokenizer(),
        encoder=EncoderBinding('a'*64, 'b'*64, max_len), protocol_sha256=hashlib.sha256(protocol).hexdigest())


def test_four_exact_plans_independently_verify():
    data = prepared()
    plans = prepare_screen(data)
    assert [(x.reported_arm, x.plan.arm, x.plan.seed) for x in plans] == list(MATRIX)
    assert all(x.plan.shape.world_size == 2 and x.plan.shape.pairs_per_rank == 8 and x.plan.shape.accumulation == 8 for x in plans)
    for x in plans:
        verify_plan(x.plan, *data.pools)
    summary = preparation_summary(plans)
    assert summary['ready_to_submit'] is False
    assert summary['source_qualification_verified_here'] is False
    assert len(summary['fits']) == 4
    assert 'card0' not in json.dumps(summary)


def test_protocol_matrix_and_parent_files_unchanged():
    obj = json.loads((ROOT/'g_reuse_development_screen_v1.json').read_bytes())
    assert [(x['arm'], x['consumer_arm'], x['seed']) for x in obj['matrix']] == list(MATRIX)
    assert obj['planned_fits'] == len(MATRIX)
    for field, file in [
        ('parent_effect_protocol_sha256', 'g_reuse_effect_protocol_v1.json'),
        ('historical_development_protocol_sha256', 'global_local_historical_development_protocol_v1.json'),
        ('frozen_calibration_v2_sha256', 'global_local_calibration_candidate_protocol_v2.json'),
    ]:
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest() == obj[field]
    assert obj['training']['exact_total_gpu_hours'] is None
    assert obj['training']['expensive_submission_authorized_by_this_file'] is False


def test_source_order_or_pair_orientation_does_not_choose_a_new_plan():
    cards, g, l = fixture()
    original = prepare_screen(prepared())
    swapped = prepare_screen(prepared((cards[::-1], [r[::-1] for r in g[::-1]], l[::-1])))
    assert original == swapped


def test_extra_global_execution_endpoint_is_rejected():
    cards, g, l = deepcopy(fixture())
    cards.append({'endpoint_id': 'global_extra', 'task_name': 'synthetic-task', 'code': 'x=9'})
    g[0] = ('card0', 'global_extra')
    with pytest.raises(PlanError, match='screen_global_not_execution_endpoint_reuse'):
        prepare_screen(prepared((cards, g, l)))


def test_non16k_not_silently_mixed_into_screen():
    with pytest.raises(PlanError, match='screen_context_mismatch'):
        prepare_screen(prepared(max_len=8192))


def test_cannot_expand_or_reselect_matrix_in_summary():
    fits = prepare_screen(prepared())
    with pytest.raises(PlanError, match='screen_matrix_mismatch'):
        preparation_summary(fits[:2])
    with pytest.raises(PlanError, match='screen_matrix_mismatch'):
        preparation_summary(fits[::-1])


def test_local_baseline_does_not_receive_global_targets():
    data = prepared()
    gkeys = {r.key for r in data.pools[0]}
    for fit in prepare_screen(data):
        requested = set(data.required_label_keys(fit.plan))
        if fit.plan.arm == 'Lbudget':
            assert requested.isdisjoint(gkeys)
        else:
            assert gkeys <= requested
