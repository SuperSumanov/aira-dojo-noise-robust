"""Offline checks of the published operational receipts; never executes repair."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results/g0_source_repair_20260904'


def load(name):
    return json.loads((RESULTS / name).read_text(encoding='utf-8'))


def test_independent_receipts_identical_and_bound():
    a = RESULTS / 'independent_verification_a.json'
    b = RESULTS / 'independent_verification_b.json'
    assert a.read_bytes() == b.read_bytes()
    receipt = load(a.name)
    for field, name in [('repair_sha256', 'repair.json'), ('before_sha256', 'before.json'),
                        ('static_assets_sha256', 'static_assets_receipt.json'),
                        ('recovery_binding_sha256', 'recovery_binding.json')]:
        assert hashlib.sha256((RESULTS/name).read_bytes()).hexdigest() == receipt[field]


def test_repair_did_not_change_experimental_contract():
    repair = load('repair.json')
    assert repair['source_clean'] and repair['reversible']
    assert repair['tracked_source_files_changed'] == 0
    assert not any(repair[k] for k in ('known_failure_gate_disabled', 'training_config_changed',
                   'frozen_protocols_changed', 'new_gpu_jobs', 'model_fits', 'whole_tree_immutable_claim'))
    assert repair['source_root_original_mode'] == 0o700
    assert repair['source_root_mode_after'] == 0o500
    assert not repair['root_writable_by_current_process']


def test_static_and_runtime_recheck_matches_original():
    old = ROOT / 'results/critic_component_g0_20260903/recovery_preflight'
    for name in ('static_assets_receipt.json', 'recovery_binding.json'):
        previous = json.loads((old/name).read_text(encoding='utf-8'))
        current = load(name)
        previous.pop('created_at_utc', None)
        current.pop('created_at_utc', None)
        assert current == previous


def test_failed_job_is_not_mistaken_for_training_or_permission():
    r = load('independent_verification_a.json')
    assert r['job_12288_failed_before_training']
    assert [(j['job_id'], j['elapsed_seconds']) for j in r['jobs']] == [(12181, 156), (12288, 4)]
    used = sum(j['allocated_gpus'] * j['elapsed_seconds'] for j in r['jobs'])
    assert used == r['allocated_gpu_seconds_used'] == 320
    assert used + 2 * r['proposed_retry_seconds'] == r['proposed_cumulative_gpu_seconds'] == 14360
    assert r['proposed_cumulative_gpu_seconds'] <= 4 * 3600
    assert not r['new_retry_authorized'] and not r['new_job_submitted']
    assert r['queue_empty'] and not r['protected_cohort_values_read']


def test_original_worker_failure_evidence_retained():
    diagnostic = load('failure_diagnostic.json')
    workers = [r for r in diagnostic['files'] if r['file'] == 'runs/job-12288/worker.log']
    assert len(workers) == 1
    worker = workers[0]
    encoded = ('\n'.join(worker['safe_operational_tail']) + '\n').encode()
    assert len(encoded) == worker['bytes'] == 115
    assert hashlib.sha256(encoded).hexdigest() == worker['sha256']
    assert worker['sha256'] == load('independent_verification_a.json')['worker_log_sha256']
    assert all(f.get('credential_shape_hits', 0) == 0 for f in diagnostic['files'])
