import json

from phase1.critic_train_projection import PinnedFile, TrainProjectionSpec, load_training_inputs
from phase1.g_reuse_development_screen_plan import prepare_screen
from phase1.scripts.validate_critic_entry_cpu_20260906 import ENCODER, PROTOCOL, Tokenizer, cases_for, fixture_layout, write_fixture


def test_accum8_reuses_endpoints_without_edge_overlap():
    cards, g, l = fixture_layout('accum8')
    endpoints = {c['endpoint_id'] for c in cards}
    assert len(endpoints) == 32 and len(g) == 130 and len(l) == 134
    assert set(g).isdisjoint(l)
    assert {x for e in l for x in e} == endpoints
    assert {x for e in g for x in e} <= endpoints
    assert len({tuple(Tokenizer()(c['code'], add_special_tokens=False)['input_ids']) for c in cards}) == 32


def test_accum8_fixed_full_tail_and_resume_plan(tmp_path):
    root = tmp_path/'inputs'
    write_fixture(root, 'accum8')
    o = json.loads((root/'spec.json').read_bytes())
    spec = TrainProjectionSpec(o['source_package_sha256'], o['split_receipt_sha256'],
        **{k: PinnedFile(**o[k]) for k in ('topology', 'local_targets', 'global_targets')})
    data = load_training_inputs(root, spec, Tokenizer(), encoder=ENCODER, protocol_sha256=PROTOCOL)
    plans = prepare_screen(data)
    assert cases_for('accum8') == [(1, 'full'), (2, 'full'), (1, 'prefix'), (1, 'resume'), (2, 'prefix'), (2, 'resume')]
    for fit in plans:
        p = fit.plan
        assert p.steps == 4 and p.shape.world_size == 2 and p.shape.pairs_per_rank == 8 and p.shape.accumulation == 8
        assert p.planned_pair_visits == 264 and p.planned_valid_tokens == 264*76
        expected = [128, 6, 128, 2] if p.arm == 'Lbudget' else [128, 2, 128, 6]
        for rank in (0, 1):
            batches = [[b for b in p.batches if b.rank == rank and b.optimizer_step == s] for s in range(4)]
            assert [len(bs) for bs in batches] == [8, 1, 8, 1]
            assert [sum(len(b.rows) for b in bs)*2 for bs in batches] == expected


def test_original_tiny_fixture_unchanged():
    cards, g, l = fixture_layout('tiny')
    assert len(cards) == 8 and len(g) == len(l) == 4
    assert cards[0]['code'] == 'x=0\n'
    assert len(cases_for('tiny')) == 8
