"""Resume only the CPU payload audit of fixed synthetic job 12664.

The original 900-second attempt is immutable. Every new rank part hashes its
three files before/after the unchanged six-role checker. Finalization rehashes
the complete bundles. No GPU/model training or real-data source admission.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from phase1.partitioned_payload_audit import (PARTS, complete_coverage, completed_part,
    fingerprint, part_name, payload_names, require, save_exclusive, verified_file)
from phase1.scripts import verify_pivot_ampere_artifacts_20260907 as original

B = Path('/research/d7/spc/yzyang4')
ROOT = B/'critic-pivot-ampere/job-12664'
OUT = B/'critic-pivot-ampere-partitioned-postflight-20260907'
OLD = B/'critic-pivot-ampere-postflight-12664-20260907/AUTHENTICATED.json'
AUTH_SHA = '522cf8f5e8d3a4ca4f033494e11dc8c7526c2035eb623469b58d30661729e7ce'
TRAIN_COMMIT = '88522f74cafcd45778751c5315fa0a89a1704965'


def deployment():
    source = Path(__file__).resolve().parents[2]
    p = source.parent/'SOURCE.json'
    record = original.read(p)
    require(record['training_commit'] == TRAIN_COMMIT and record['tests_passed'] is True
            and re.fullmatch('[0-9a-f]{40}', record['audit_commit']) is not None,
            'unqualified_partitioned_deployment')
    for name, digest in record['files'].items():
        require(original.sha(source/name) == digest, 'partitioned_source_drift')
    require(Path(original.__file__).resolve() == source/'phase1/scripts/verify_pivot_ampere_artifacts_20260907.py',
            'legacy_checker_import_origin')
    return {'audit_commit': record['audit_commit'], 'source_receipt_sha256': original.sha(p),
            'training_commit': TRAIN_COMMIT, 'authenticated_receipt_sha256': AUTH_SHA,
            'job_id': '12664'}


def authenticate_shared():
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'cpu_only_audit_required')
    require(not Path('/proc/1946993').exists(), 'previous_checker_pid_present')
    require(original.sha(OLD) == AUTH_SHA, 'previous_authentication_drift')
    auth = original.read(OLD)
    require(auth['source_commit'] == TRAIN_COMMIT and auth['job_id'] == '12664', 'wrong_authenticated_job')
    require(original.sha(Path(original.__file__)) == auth['verifier_sha256'], 'original_checker_changed')
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    text = subprocess.check_output(['sacct', '-X', '-n', '-P', '-j', '12664',
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'], env=env, timeout=30).decode().strip()
    require(len(text.splitlines()) == 1, 'ambiguous_slurm_receipt')
    jid, status, elapsed, tres, rc = text.split('|')[:5]
    require(jid == '12664' and status == 'COMPLETED' and elapsed == '2729'
            and 'gres/gpu=2' in tres.split(',') and rc == '0:0', 'slurm_terminal_drift')
    ready = original.read(original.SUB/'READY.json')
    require(ready['commit'] == TRAIN_COMMIT, 'original_release_changed')
    require(original.read(original.SUB/'RELEASED.json') == {'job_id': '12664', 'commit': TRAIN_COMMIT},
            'original_release_changed')
    for name, h in ready['hashes'].items():
        require(original.sha(Path(ready['control'])/name) == h, 'original_source_changed')
    for name, h in ready['evidence_hashes'].items():
        require(original.sha(original.SUB/name) == h, 'original_preparation_changed')
    # Exact original scan receipts: no rescanning changed text or new roots.
    for name, evidence in auth['text_receipts'].items():
        verified_file(ROOT/name, evidence)
    matrices = {}
    expected = set(auth['text_receipts'])
    for case, step in (('prefix1', 1), ('resume2', 2)):
        cp = ROOT/'trajectories'/case/f'checkpoint-{step}'
        require(original.sha(cp/'manifest.json') == auth['checkpoint_manifest_sha256'][case],
                'authenticated_manifest_changed')
        m = original.read(cp/'manifest.json')
        require(m['completed_steps'] == step and m['cumulative_valid_tokens'] == step*4194304
                and set(m['files']) == original.expected_members(), 'checkpoint_manifest_scope')
        require({p.relative_to(cp).as_posix() for p in cp.rglob('*') if p.is_file()}
                == original.expected_members() | {'manifest.json'}, 'checkpoint_inventory_changed')
        require({p.relative_to(cp).as_posix() for p in cp.rglob('*') if p.is_dir()} == {'pytorch_model'},
                'checkpoint_directory_changed')
        for name, record in m['files'].items():
            require(fingerprint(cp/name)['bytes'] == record['bytes'], 'checkpoint_size_changed')
            if name.endswith(('.pt', '.pkl')):
                expected.add((cp/name).relative_to(ROOT).as_posix())
        matrices[case] = (cp, m)
    require({p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()} == expected,
            'job_inventory_changed')
    require(not any(p.is_symlink() for p in ROOT.rglob('*')), 'job_symlink')
    return auth, matrices


def event(folder, phase, start):
    value = {'phase': phase, 'elapsed_seconds': time.monotonic()-start,
             'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (folder/'progress.jsonl').open('a') as stream:
        stream.write(json.dumps(value, sort_keys=True)+'\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(value, sort_keys=True), flush=True)


def part(case, rank):
    name = part_name(case, rank)
    binding = deployment()
    auth, matrices = authenticate_shared()
    cp, manifest = matrices[case]
    folder = OUT/name
    if folder.exists():
        done = completed_part(folder, binding, case, rank)
        for n, fp in done['input_fingerprints'].items():
            require(fingerprint(cp/n) == fp, 'completed_part_file_metadata_changed')
        print(json.dumps({'status': 'CACHED_PART_REQUIRES_FINAL_REHASH', 'part': name})); return
    folder.mkdir(mode=0o700)
    save_exclusive(folder/'INTENT.json', {'binding': binding, 'case': case, 'rank': rank})
    started = time.monotonic()
    try:
        event(folder, 'hash_pre_start', started)
        names = payload_names(rank)
        before = {n: verified_file(cp/n, manifest['files'][n]) for n in names}
        event(folder, 'hash_pre_done', started)
        import torch
        from phase1.critic_zero3_payload_observation import verify_payload_observation
        torch.set_num_threads(1)
        require(not torch.cuda.is_initialized(), 'unexpected_cuda_context')
        event(folder, 'load_start', started)
        payload = [torch.load(cp/n, map_location='cpu', weights_only=False, mmap=n.endswith('.pt')) for n in names]
        event(folder, 'load_done', started)
        step = 1 if case == 'prefix1' else 2
        result = verify_payload_observation(*payload, original.read(cp/f'observed_{rank}.json'),
            binding=manifest['binding'], step=step, tokens=step*4194304, parameters=original.PARAMETERS)
        event(folder, 'payload_checks_done', started)
        del payload
        require(not torch.cuda.is_initialized(), 'unexpected_cuda_context')
        require({n: verified_file(cp/n, manifest['files'][n]) for n in names} == before, 'payload_posthash_drift')
        require(original.sha(cp/'manifest.json') == auth['checkpoint_manifest_sha256'][case], 'manifest_drift_after_part')
        require(deployment() == binding and original.sha(OLD) == AUTH_SHA, 'part_source_changed')
        event(folder, 'hash_post_done', started)
        receipt = {'classification': 'ONE_AUTHENTICATED_PAYLOAD_PART_NOT_FINAL_ACCEPTANCE',
            'binding': binding, 'case': case, 'rank': rank, 'input_fingerprints': before,
            'payload_check': result, 'elapsed_seconds': time.monotonic()-started}
        digest = save_exclusive(folder/'SUCCESS.json', receipt)
        (folder/'progress.jsonl').chmod(0o400)
        save_exclusive(folder/'COMPLETE.json', {'sha256': digest})
        print(json.dumps({'status': 'PAYLOAD_PART_PASS_NOT_FINAL', 'part': name, 'receipt_sha256': digest}), flush=True)
    except BaseException as exc:
        save_exclusive(folder/'FAILED.json', {'exception': type(exc).__name__,
            'reason_sha256': hashlib.sha256(str(exc).encode()).hexdigest()})
        raise


def finalize():
    binding = deployment()
    auth, matrices = authenticate_shared()
    require(not (OUT/'FINAL.json').exists(), 'final_already_present')
    checks = [completed_part(OUT/part_name(case, rank), binding, case, rank) for case, rank in PARTS]
    complete_coverage(checks)
    for case, step in (('prefix1', 1), ('resume2', 2)):
        cp, m = matrices[case]
        require(original.manifest(cp, m['binding'], step) == m, 'final_full_bundle_hash_drift')
        for value in (v for v in checks if v['case'] == case):
            rank = value['rank']; result = value['payload_check']; observed = original.read(cp/f'observed_{rank}.json')
            require(result['parameters'] == original.PARAMETERS and result['completed_steps'] == step
                    and result['cumulative_valid_tokens'] == step*4194304, 'final_payload_cursor')
            require(result['direct_state_sha256'] == {k: observed['state'][k] for k in result['direct_roles_verified']},
                    'final_live_payload_binding')
            require(all(fingerprint(cp/n) == fp for n, fp in value['input_fingerprints'].items()), 'final_metadata_drift')
    require(deployment() == binding and original.sha(OLD) == AUTH_SHA, 'final_source_drift')
    result = {'classification': 'REAL_AMPERE_PIVOT_PARTITIONED_SIX_ROLE_PAYLOAD_ACCEPTED_NOT_EFFECT_OR_FULL_PARITY',
        'binding': binding, 'actual_payload_checks': checks, 'segments': auth['segments'],
        'parameters': original.PARAMETERS, 'job_elapsed_seconds': 2729, 'allocated_gpu_seconds': 5458,
        'source_admission': False, 'model_effect_measured': False, 'full_size_uninterrupted_final_parity_measured': False,
        'previous_attempt_limit_seconds': 900, 'previous_attempt_preserved': True,
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    digest = save_exclusive(OUT/'FINAL.json', result)
    print(json.dumps({'status': result['classification'], 'receipt_sha256': digest}), flush=True)


def wall_limit(*_):
    raise TimeoutError('partition_wall_limit')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('prefix1', 'resume2'))
    parser.add_argument('--rank', type=int, choices=(0, 1))
    parser.add_argument('--finalize', action='store_true')
    args = parser.parse_args()
    require(OUT.is_dir() and not OUT.is_symlink(), 'missing_audit_root')
    os.umask(0o077)
    # A second boundary survives loss of the outer foreground supervisor.
    signal.signal(signal.SIGALRM, wall_limit)
    signal.alarm(900)
    if args.finalize:
        require(args.case is None and args.rank is None, 'ambiguous_audit_action'); finalize()
    else:
        require(args.case is not None and args.rank is not None, 'missing_part_address'); part(args.case, args.rank)
    signal.alarm(0)


if __name__ == '__main__':
    main()
