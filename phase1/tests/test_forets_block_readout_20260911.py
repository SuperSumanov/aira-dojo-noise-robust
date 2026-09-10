"""Artificial final events only; never read actual candidate results/cohorts."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

PHASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PHASE))
import forets_block_readout_20260911 as r


def put(path, value, *, indent=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=indent) + '\n').encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def case(tmp_path):
    raw = (PHASE/'results/forets_next_package_20260911/prepared.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == r.PREPARED_SHA
    prepared = json.loads(raw)
    prepared['output'] = str(tmp_path)
    manifest = dict(schema=1, role=r.ROLE, source_tree=r.TREE, prepared_sha256=r.PREPARED_SHA,
                    controller_commit='a'*40, blocks=[], runs=[])
    for block in (1, 2):
        manifest['blocks'].append(dict(block=block, allocation_id=str(1000+block), node='gpu28', state='COMPLETED',
            elapsed_seconds=1800, allocated_gpus=2, service_startup_seconds=100,
            observed_utc='2026-09-11T00:00:00+00:00'))
    for original in prepared['run_configs']:
        run_id = original['run_id']
        cfg = {k:original[k] for k in ('run_id','seed','task','arm')}
        cfg['artificial_fixture'] = True
        digest = put(tmp_path/'configs'/f'{run_id}.json', cfg)
        original['config_sha256'] = digest
        cfg_rel = f"runs/srun_pool/block{original['block']}/configs/{run_id}.json"
        process_rel = f"runs/srun_pool/block{original['block']}/identities/{run_id}.attempt-1.bounded/execution/summary.json"
        runtime_sha = put(tmp_path/cfg_rel, cfg, indent=2)  # Same values, different byte serialization.
        put(tmp_path/process_rel, dict(status='completed', started=True, returncode=0, elapsed_seconds=100))
        # Both tasks exercise positive AND negative paired effects, with exact binary fractions.
        if original['task'] == 'leaf-classification':
            score = (2 if original['arm']=='uniform_random' else 1) if original['seed']==8 else (1 if original['arm']=='uniform_random' else 2)
        else:
            score = (.25 if original['seed']==8 else .75) if original['arm']=='uniform_random' else .5
        put(tmp_path/f'runs/{run_id}/json/eval.jsonl', dict(data=dict(score=score, selected_node_id='artificial-final-node')))
        manifest['runs'].append(dict(**{k:original[k] for k in ('run_id','block','task','seed','arm')},
            run_dir='runs/'+run_id, prepared_config_sha256=digest,
            runtime_config_path=cfg_rel, runtime_config_sha256=runtime_sha,
            process_summary=process_rel, runtime_status='completed'))
    return tmp_path, prepared, manifest


def test_directions_variance_and_no_resource_double_count(case):
    root, prepared, manifest = case
    result = r.summarize(manifest, prepared, root)
    assert len(result['runs']) == 8 and result['comparable_pairs'] == 4
    assert [x['improvement'] for x in result['pairs']] == [1, -1, .25, -.25]
    assert [x['median_improvement'] for x in result['tasks']] == [0, 0]
    assert result['tasks'][0]['sample_stdev_improvement'] == pytest.approx(2**.5)
    assert result['total_allocation_gpu_hours'] == 2  # Two blocks, not eight rows.
    assert len(result['blocks']) == 2
    assert all(x['api_cost_usd'] is None for x in result['runs'])
    assert all('gpu_hours' not in x for x in result['runs'])


def test_failed_worker_with_final_score_is_not_a_win(case):
    root, prepared, manifest = case
    row = manifest['runs'][1]
    row['runtime_status'] = 'failed'
    put(root/row['process_summary'], dict(status='failed', started=True, returncode=1, elapsed_seconds=100))
    result = r.summarize(manifest, prepared, root)
    assert result['runs'][1]['final_score_observed'] == 1
    assert result['runs'][1]['comparable_score'] is None
    assert result['pairs'][0]['improvement'] is None
    assert len(result['runs']) == 8 and result['comparable_pairs'] == 3


def test_unstarted_slot_is_retained_and_stale_event_not_read(case, monkeypatch):
    root, prepared, manifest = case
    row = manifest['runs'][0]
    row.update(runtime_status='not_started', runtime_config_path=None, runtime_config_sha256=None, process_summary=None)
    old = r._final_event
    def guarded(path, task):
        assert row['run_id'] not in str(path)
        return old(path, task)
    monkeypatch.setattr(r, '_final_event', guarded)
    result = r.summarize(manifest, prepared, root)
    assert len(result['runs']) == 8 and result['runs'][0]['process_status'] == 'not_started'
    assert result['runs'][0]['final_score_observed'] is None


@pytest.mark.parametrize('problem', ['missing', 'duplicate', 'nonfinite'])
def test_invalid_final_is_not_replaced_by_zero_or_another_event(case, problem):
    root, prepared, manifest = case
    event = root/(manifest['runs'][0]['run_dir']+'/json/eval.jsonl')
    if problem == 'missing': event.unlink()
    elif problem == 'duplicate': event.write_bytes(event.read_bytes()*2)
    else: put(event, dict(data=dict(score=float('nan'), selected_node_id='artificial')))
    result = r.summarize(manifest, prepared, root)
    assert result['runs'][0]['comparable_score'] is None
    assert result['pairs'][0]['improvement'] is None and result['comparable_pairs'] == 3


@pytest.mark.parametrize('problem', ['seed','prepared_hash','runtime_hash','config_value','escape','missing_slot','wrong_role','open_block','open_run'])
def test_bad_metadata_rejected_before_outcome_reads(case, monkeypatch, problem):
    root, prepared, manifest = case
    row = manifest['runs'][0]
    if problem == 'seed': row['seed'] = 6
    elif problem == 'prepared_hash': row['prepared_config_sha256'] = '0'*64
    elif problem == 'runtime_hash': row['runtime_config_sha256'] = '0'*64
    elif problem == 'config_value':
        row['runtime_config_sha256'] = put(root/row['runtime_config_path'], {'changed': True})
    elif problem == 'escape': row['process_summary'] = '../outside.json'
    elif problem == 'missing_slot': manifest['runs'].pop()
    elif problem == 'wrong_role': manifest['role'] = 'forets_e2e_development'
    elif problem == 'open_block': manifest['blocks'][1]['state'] = 'RUNNING'
    elif problem == 'open_run': row['runtime_status'] = 'running'
    def forbidden(*_): raise AssertionError('metadata must fail before result reads')
    monkeypatch.setattr(r, '_final_event', forbidden); monkeypatch.setattr(r, '_process', forbidden)
    with pytest.raises(ValueError): r.summarize(manifest, prepared, root)


def test_duplicate_allocation_refused_and_unknown_time_not_zero(case):
    root, prepared, manifest = case
    manifest['blocks'][0]['elapsed_seconds'] = None
    manifest['blocks'][0]['service_startup_seconds'] = None
    result = r.summarize(manifest, prepared, root)
    assert result['total_allocation_gpu_hours'] is None and result['known_allocation_gpu_hours'] == 1
    assert result['unmeasured_allocated_blocks'] == 1
    manifest['blocks'][1]['allocation_id'] = manifest['blocks'][0]['allocation_id']
    with pytest.raises(ValueError, match='counted'): r.summarize(manifest, prepared, root)


def test_unstarted_block_has_no_invented_allocation(case):
    root, prepared, manifest = case
    manifest['blocks'][1].update(state='NOT_STARTED', allocation_id=None, node=None, elapsed_seconds=None,
                                  allocated_gpus=None, service_startup_seconds=None)
    for row in manifest['runs'][4:]:
        row.update(runtime_status='not_started', runtime_config_path=None, runtime_config_sha256=None, process_summary=None)
    result = r.summarize(manifest, prepared, root)
    assert result['comparable_pairs'] == 2 and len(result['runs']) == 8
    assert result['total_allocation_gpu_hours'] == 1 and result['blocks'][1]['gpu_hours'] is None


def test_budget_overrun_reported_not_clipped(case):
    root, prepared, manifest = case
    manifest['blocks'][0]['elapsed_seconds'] = 18000
    result = r.summarize(manifest, prepared, root)
    assert result['blocks'][0]['gpu_hours'] == 10 and result['blocks'][0]['nominal_budget_exceeded'] is True


def test_csv_all_slots_exclusive_output_and_blanks(case):
    root, prepared, manifest = case
    event = root/(manifest['runs'][0]['run_dir']+'/json/eval.jsonl'); event.unlink()
    output = root/'new-report'
    result = r.summarize(manifest, prepared, root); r.write_report(result, output)
    with (output/'runs.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 8 and rows[0]['comparable_score'] == ''
    assert len(list(csv.DictReader((output/'blocks.csv').read_text().splitlines()))) == 2
    with pytest.raises(FileExistsError): r.write_report(result, output)


def test_cli_requires_pinned_preparation_before_manifest(case, monkeypatch):
    root, prepared, manifest = case
    # Exercise the real CLI against explicitly marked artificial fixture files.
    digest = put(root/'prepared.json', prepared)
    manifest['prepared_sha256'] = digest
    put(root/'runtime.json', manifest)
    monkeypatch.setattr(r, 'ROOT', root); monkeypatch.setattr(r, 'PREPARED_SHA', digest)
    monkeypatch.setattr(sys, 'argv', ['reader','--runtime-manifest','runtime.json','--output',str(root/'cli-report')])
    r.main()
    assert json.loads((root/'cli-report/summary.json').read_text())['planned_runs'] == 8
