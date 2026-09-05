import copy
from dataclasses import asdict
import hashlib
import json

import pytest

from phase1.critic_train_projection import PinnedFile
from phase1.critic_training_definition import load_definition, launch_attempt
from phase1.global_local_execution_plan import PlanError


def fixture(tmp_path):
    obj = {'protocol': 'critic-development-training-definition-v1',
        'model': {'fixture': 'random-tiny'}, 'projection': {'source': 'a'*64},
        'encoder': {'max_len': 16384}, 'shape': {'world_size': 2},
        'screen_protocol_sha256': 'b'*64, 'training_source_manifest_sha256': 'c'*64,
        'runtime_manifest_sha256': 'd'*64,
        'fits': {str(i): {'plan_sha256': str(i)*64, 'total_steps': 4, 'valid_tokens': 20064} for i in range(1, 5)}}
    raw = json.dumps(obj, sort_keys=True).encode()
    (tmp_path/'definition.json').write_bytes(raw)
    attempt = {'output': str(tmp_path/'prefix'), 'stop_after': 2, 'checkpoint_steps': [2],
        'resume': None, 'resume_manifest_sha256': None}
    launch = {'protocol': 'critic-development-launch-v2', 'release_id': 'fixture-prefix',
        'training_definition': asdict(PinnedFile('definition.json', hashlib.sha256(raw).hexdigest(), len(raw))),
        'fits': {'1': attempt}}
    return obj, launch


def test_old_whole_launch_binding_changes_on_a_legal_resume(tmp_path):
    _, prefix = fixture(tmp_path)
    resume = copy.deepcopy(prefix)
    resume['release_id'] = 'fixture-resume'
    resume['fits']['1'].update(output=str(tmp_path/'resumed'), stop_after=4, checkpoint_steps=[4],
        resume=str(tmp_path/'prefix'/'checkpoint-2'), resume_manifest_sha256='e'*64)
    rawsha = lambda obj: hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
    assert rawsha(prefix) != rawsha(resume)  # Reproduces the previous identity problem.
    before, sha = load_definition(tmp_path, prefix)
    after, new_sha = load_definition(tmp_path, resume)
    assert before == after and sha == new_sha
    assert launch_attempt(prefix, before, 1) != launch_attempt(resume, after, 1)


@pytest.mark.parametrize('field', ['model', 'projection', 'encoder', 'shape', 'fits',
    'screen_protocol_sha256', 'training_source_manifest_sha256', 'runtime_manifest_sha256'])
def test_changed_science_cannot_keep_the_checkpoint_identity(tmp_path, field):
    obj, launch = fixture(tmp_path)
    if isinstance(obj[field], dict): obj[field]['different'] = True
    else: obj[field] = 'f'*64
    (tmp_path/'definition.json').write_bytes(json.dumps(obj, sort_keys=True).encode())
    with pytest.raises(PlanError): load_definition(tmp_path, launch)


@pytest.mark.parametrize('bad', ['old_protocol', 'unknown_definition_key', 'missing_plan', 'plan_bool',
                                  'extra_attempt_science', 'resume_without_hash', 'unsafe_output', 'too_many_steps'])
def test_invalid_contracts(tmp_path, bad):
    obj, launch = fixture(tmp_path)
    if bad == 'old_protocol': launch['protocol'] = 'critic-development-launch-v1'
    if bad == 'unknown_definition_key': obj['resume'] = '/tmp/other'
    if bad == 'missing_plan': del obj['fits']['4']
    if bad == 'plan_bool': obj['fits']['1']['total_steps'] = True
    if bad == 'extra_attempt_science': launch['fits']['1']['learning_rate'] = 2e-5
    if bad == 'resume_without_hash': launch['fits']['1']['resume'] = str(tmp_path/'prefix'/'checkpoint-2')
    if bad == 'unsafe_output': launch['fits']['1']['output'] = '../outside'
    if bad == 'too_many_steps': launch['fits']['1']['stop_after'] = 5
    raw = json.dumps(obj, sort_keys=True).encode()
    (tmp_path/'definition.json').write_bytes(raw)
    launch['training_definition'].update(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    with pytest.raises(PlanError):
        definition, _ = load_definition(tmp_path, launch)
        launch_attempt(launch, definition, 1)
