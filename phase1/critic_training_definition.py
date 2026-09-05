"""Stable training identity, separate from an individual launch attempt.

Caller must FIRST admit the exact launch contract. This reader is not a source,
GPU, budget or release authority. A resumed attempt may change output/stop/resume
locations; its checkpoint still binds the exact immutable definition bytes.
Scientific inputs, runtime/code bindings and all four plans remain in that file.
"""
from pathlib import Path
import re

from phase1.critic_train_projection import PinnedFile, read_pinned
from phase1.global_local_execution_plan import PlanError


DEFINITION_KEYS = {'protocol', 'model', 'projection', 'encoder',
    'screen_protocol_sha256', 'shape', 'fits', 'training_source_manifest_sha256',
    'runtime_manifest_sha256'}
ATTEMPT_KEYS = {'output', 'stop_after', 'checkpoint_steps', 'resume', 'resume_manifest_sha256'}


def require(ok, reason):
    if not ok:
        raise PlanError(reason)


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def load_definition(root, admitted_launch):
    require(type(admitted_launch) is dict
            and admitted_launch.get('protocol') == 'critic-development-launch-v2',
            'stable_definition_requires_launch_v2')
    record = admitted_launch.get('training_definition')
    require(type(record) is dict and set(record) == {'name', 'sha256', 'size'},
            'training_definition_file_binding')
    pinned = PinnedFile(**record)
    obj = read_pinned(Path(root), pinned)
    require(set(obj) == DEFINITION_KEYS
            and obj['protocol'] == 'critic-development-training-definition-v1',
            'training_definition_schema')
    require(all(type(obj[k]) is dict and bool(obj[k]) for k in ('model', 'projection', 'encoder', 'shape')),
            'training_definition_mapping')
    require(all(is_sha(obj[k]) for k in ('screen_protocol_sha256',
            'training_source_manifest_sha256', 'runtime_manifest_sha256')), 'training_definition_hashes')
    require(type(obj['fits']) is dict and set(obj['fits']) == {'1', '2', '3', '4'},
            'training_definition_four_plans')
    for fit in obj['fits'].values():
        require(type(fit) is dict and set(fit) == {'plan_sha256', 'total_steps', 'valid_tokens'}
                and is_sha(fit['plan_sha256'])
                and all(type(fit[k]) is int and fit[k] > 0 for k in ('total_steps', 'valid_tokens')),
                'training_definition_plan')
    return obj, pinned.sha256


def launch_attempt(launch, definition, sequence):
    require(type(sequence) is int and 1 <= sequence <= 4, 'training_fit_sequence')
    attempts = launch.get('fits')
    require(type(attempts) is dict and set(attempts) <= {'1', '2', '3', '4'}
            and str(sequence) in attempts, 'launch_attempt_sequence')
    row = attempts[str(sequence)]
    require(type(row) is dict and set(row) == ATTEMPT_KEYS, 'launch_attempt_schema')
    end = row['stop_after']
    require(type(end) is int and 1 <= end <= definition['fits'][str(sequence)]['total_steps'],
            'launch_attempt_stop')
    schedule = row['checkpoint_steps']
    require(type(schedule) is list and bool(schedule)
            and all(type(x) is int and 1 <= x <= end for x in schedule)
            and schedule == sorted(set(schedule)) and schedule[-1] == end,
            'launch_attempt_checkpoint_schedule')
    def absolute(value):
        return type(value) is str and Path(value).is_absolute() and '..' not in Path(value).parts
    require(absolute(row['output']), 'launch_attempt_output')
    require((row['resume'] is None and row['resume_manifest_sha256'] is None)
            or (absolute(row['resume']) and is_sha(row['resume_manifest_sha256'])),
            'launch_attempt_resume_binding')
    # The full verified session restore, not this schema, checks cursor/tokens,
    # old/new state equality, exact manifest bytes and all checkpoint members.
    return dict(row)
