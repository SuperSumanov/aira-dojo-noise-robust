from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from phase1.critic_train_projection import PinnedFile, TrainProjectionSpec, load_training_inputs, load_training_targets
from phase1.g_reuse_development_screen_plan import prepare_screen
from phase1.global_local_execution_plan import EncoderBinding, PlanError
from phase1.tests.test_g_reuse_development_screen_plan import Tokenizer, fixture


def put(root, name, obj):
    raw = json.dumps(obj, sort_keys=True).encode()
    (root/name).write_bytes(raw)
    return PinnedFile(name, hashlib.sha256(raw).hexdigest(), len(raw))


def inputs(root, role='train'):
    cards, g, l = fixture()
    header = {'role': role, 'source_package_sha256': 'a'*64, 'split_receipt_sha256': 'b'*64}
    top = put(root, 'topology.json', dict(header, protocol='critic-train-topology-v1', cards=cards,
                                         global_edges=g, local_edges=l))
    placeholder = PinnedFile('local.json', 'c'*64, 1)
    spec = TrainProjectionSpec('a'*64, 'b'*64, top, placeholder, replace(placeholder, name='global.json'))
    if role != 'train':
        return spec
    prepared = load_training_inputs(root, spec, Tokenizer(), encoder=EncoderBinding('d'*64, 'e'*64, 16384),
                                    protocol_sha256='f'*64)
    files = {}
    for source, pool, name in [('G', prepared.pools[0], 'global.json'), ('L', prepared.pools[1], 'local.json')]:
        files[source] = put(root, name, dict(header, protocol='critic-train-targets-v1', source=source,
                                            winners={r.key: r.a.card_id for r in pool}))
    return replace(spec, local_targets=files['L'], global_targets=files['G']), prepared


def test_all_four_plans_read_only_required_targets(tmp_path, monkeypatch):
    spec, data = inputs(tmp_path)
    from phase1 import critic_train_projection as module
    original = module.read_pinned
    seen = []
    def read(root, file):
        seen.append(file.name)
        return original(root, file)
    monkeypatch.setattr(module, 'read_pinned', read)
    for fit in prepare_screen(data):
        seen.clear()
        truth = load_training_targets(tmp_path, spec, data, plan=fit.plan)
        assert seen == (['local.json'] if fit.plan.arm == 'Lbudget' else ['local.json', 'global.json'])
        assert all(truth(k) == 1 for k in data.required_label_keys(fit.plan))


def test_local_baseline_never_opens_unreadable_global_labels(tmp_path):
    spec, data = inputs(tmp_path)
    (tmp_path/'global.json').unlink()
    baseline = prepare_screen(data)[0].plan
    load_training_targets(tmp_path, spec, data, plan=baseline)
    with pytest.raises(FileNotFoundError):
        load_training_targets(tmp_path, spec, data, plan=prepare_screen(data)[1].plan)


@pytest.mark.parametrize('role', ['dev', 'test', 'first-960', 'Target-300', 'Target-522'])
def test_forbidden_roles_rejected(tmp_path, role):
    spec = inputs(tmp_path, role)
    with pytest.raises(PlanError, match='projection_not_training_role'):
        load_training_inputs(tmp_path, spec, Tokenizer(), encoder=EncoderBinding('d'*64, 'e'*64, 16384), protocol_sha256='f'*64)


@pytest.mark.parametrize('failure', ['hash', 'source', 'split', 'global_source', 'extra', 'winner', 'role'])
def test_target_failures(tmp_path, failure):
    spec, data = inputs(tmp_path)
    obj = json.loads((tmp_path/'local.json').read_bytes())
    if failure == 'source': obj['source_package_sha256'] = '0'*64
    if failure == 'split': obj['split_receipt_sha256'] = '0'*64
    if failure == 'global_source': obj['source'] = 'G'
    if failure == 'extra': obj['winners']['0'*64] = 'unknown'
    if failure == 'winner': obj['winners'][next(iter(obj['winners']))] = 'unknown'
    if failure == 'role': obj['role'] = 'dev'
    changed = put(tmp_path, 'local.json', obj)
    if failure == 'hash':
        changed = replace(changed, sha256='0'*64)
    spec = replace(spec, local_targets=changed)
    with pytest.raises(PlanError):
        load_training_targets(tmp_path, spec, data, plan=prepare_screen(data)[0].plan)


def test_topology_cannot_carry_hidden_targets_or_unbound_files(tmp_path):
    spec, _ = inputs(tmp_path)
    obj = json.loads((tmp_path/'topology.json').read_bytes())
    obj['dev_path'] = 'forbidden.json'
    spec = replace(spec, topology=put(tmp_path, 'topology.json', obj))
    with pytest.raises(PlanError, match='projection_topology_schema'):
        load_training_inputs(tmp_path, spec, Tokenizer(), encoder=EncoderBinding('d'*64, 'e'*64, 16384), protocol_sha256='f'*64)


@pytest.mark.parametrize('name', ['../train.json', '/train.json', 'train\\cards.json', 'dev.jsonl', 'train.json:stream'])
def test_path_aliases_rejected(name):
    with pytest.raises(PlanError, match='projection_filename'):
        PinnedFile(name, 'a'*64, 1)


def test_no_other_files_opened(tmp_path, monkeypatch):
    spec, _ = inputs(tmp_path)
    (tmp_path/'dev.json').write_text('UNREADABLE EVALUATION FILE')
    original = Path.open
    seen = []
    def opened(path, *args, **kwargs):
        seen.append(path.name)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    data = load_training_inputs(tmp_path, spec, Tokenizer(), encoder=EncoderBinding('d'*64, 'e'*64, 16384), protocol_sha256='f'*64)
    load_training_targets(tmp_path, spec, data, plan=prepare_screen(data)[0].plan)
    assert seen == ['topology.json', 'local.json']
