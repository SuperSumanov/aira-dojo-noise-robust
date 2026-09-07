"""Independent receipt-chain review and exact-byte export; no tensor imports.

This does not reimplement six-role tensor validation or reread large payloads.
It independently checks evidence coverage, binding, metadata and trace hashes.
Run only after the foreground supervisor has finished successfully.
"""
import csv
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import unittest

B = Path('/research/d7/spc/yzyang4')
C = 'c7c0aa4a0181be51d7c38dfa1942c6b68ca353e9'
T = '88522f74cafcd45778751c5315fa0a89a1704965'
D = B/'partitioned-postflight-source-c7c0aa4-r2-20260907'
O = B/'critic-pivot-ampere-partitioned-postflight-20260907'
ROOT = B/'critic-pivot-ampere/job-12664'
E = B/'partitioned-postflight-safe-export-20260907'
AUTH = B/'critic-pivot-ampere-postflight-12664-20260907/AUTHENTICATED.json'
AUTH_SHA = '522cf8f5e8d3a4ca4f033494e11dc8c7526c2035eb623469b58d30661729e7ce'
SOURCE_SHA = '9328c4fefebb2f92302a06c166ce318a39759ec128f77ece595ec89caa5bdbbf'
CASES = ('prefix1', 'resume2')
PARTS = [(c, r) for c in CASES for r in (0, 1)]
ROLES = ['adamw', 'master_shards', 'numpy_rng', 'python_rng', 'scaler', 'torch_rng']
PHASES = ['hash_pre_start', 'hash_pre_done', 'load_start', 'load_done', 'payload_checks_done', 'hash_post_done']
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
DENY = (b'/prospective_decision_v1/', b'decision_frozen_v11_', b'/target522-', b'/target300-',
        b'/label_vault/', b'/outcome_vault/', b'/prediction_escrow/', b'/external/senior_data/', b'first-960', b'first960')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def unique(items):
    out = {}
    for k, v in items:
        need(k not in out, 'duplicate_json'); out[k] = v
    return out


def shape(p, sealed=False):
    need(p.is_absolute() and p.resolve(strict=True) == p and p.is_file()
         and not any(q.is_symlink() for q in (p, *p.parents)), 'unsafe_file')
    s = p.stat()
    need(s.st_nlink == 1 and s.st_uid == os.getuid(), 'file_ownership')
    need(not sealed or not s.st_mode & 0o222, 'not_sealed')
    return dict(dev=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def raw(p, sealed=False):
    before = shape(p, sealed)
    need(0 <= before['bytes'] <= 2**20, 'small_text_only')
    data = p.read_bytes()
    need(not SECRET.search(data) and shape(p, sealed) == before, 'text_secret_or_drift')
    return data


def sha(p):
    return hashlib.sha256(raw(p)).hexdigest()


def read(p, sealed=False):
    return json.loads(raw(p, sealed), object_pairs_hook=unique)


def check_exit(value, stage):
    need(value['stage'] == stage and type(value['returncode']) is int and value['returncode'] == 0
         and value['timed_out'] is False and value['trace_security_passed'] is True, 'stage_exit_not_pass')
    need(type(value['elapsed_seconds']) in (int, float) and math.isfinite(value['elapsed_seconds'])
         and 0 < value['elapsed_seconds'] < 920, 'stage_timing')


def check_progress(rows):
    need([v['phase'] for v in rows] == PHASES, 'progress_coverage')
    times = [v['elapsed_seconds'] for v in rows]
    need(all(type(t) in (int, float) and math.isfinite(t) and 0 <= t < 900 for t in times)
         and times == sorted(times), 'progress_time')
    stamps = [datetime.datetime.fromisoformat(v['utc']) for v in rows]
    need(all(t.tzinfo for t in stamps) and stamps == sorted(stamps), 'progress_utc')


def scan_trace(path, expected):
    before = shape(path); h = hashlib.sha256(); count = 0
    with path.open('rb') as stream:
        for line in stream:
            need(not SECRET.search(line) and not any(marker in line for marker in DENY), 'trace_security')
            h.update(line); count += 1
    need(shape(path) == before and count == expected['trace_lines'] > 0
         and h.hexdigest() == expected['trace_sha256'], 'trace_drift')


def review():
    need(not E.exists(), 'export_already_exists')
    final = read(O/'FINAL.json', True)
    source = read(D/'SOURCE.json', True)
    auth = read(AUTH)
    need(sha(D/'SOURCE.json') == SOURCE_SHA and sha(AUTH) == AUTH_SHA, 'root_binding')
    old_attempt = B/'completion-safe-export-20260907-0909/session_observation.json'
    need(sha(old_attempt) == '3a94ca7378130f446591cd844ea236331f5009ded8871ff742b5bf8acf26ea4f'
         and not (AUTH.parent/'VERIFIED.json').exists(), 'original_timeout_evidence_changed')
    binding = dict(audit_commit=C, training_commit=T, job_id='12664',
                   source_receipt_sha256=SOURCE_SHA, authenticated_receipt_sha256=AUTH_SHA)
    need(final['binding'] == binding and source['audit_commit'] == C and source['training_commit'] == T,
         'commit_binding')
    need(final['classification'] == 'REAL_AMPERE_PIVOT_PARTITIONED_SIX_ROLE_PAYLOAD_ACCEPTED_NOT_EFFECT_OR_FULL_PARITY'
         and final['source_admission'] is False and final['model_effect_measured'] is False
         and final['full_size_uninterrupted_final_parity_measured'] is False
         and final['previous_attempt_preserved'] is True and final['previous_attempt_limit_seconds'] == 900,
         'claim_boundary')
    need(final['parameters'] == 1720577025 and final['allocated_gpu_seconds'] == 5458
         and final['job_elapsed_seconds'] == 2729 and final['segments'] == auth['segments'], 'training_facts')
    ready = read(B/'critic-pivot-ampere/submission-20260907-r3/READY.json')
    for name, digest in source['files'].items():
        p = D/'source'/name; need(sha(p) == digest, 'source_hash')
        shape(p, True)
        ref = T if name in ready['hashes'] else C
        data = subprocess.check_output(['git', '-C', str(B/'aira-dojo'), 'show', ref+':'+name], timeout=20)
        need(hashlib.sha256(data).hexdigest() == digest, 'git_source_binding')
    need(len(source['files']) == 68 and source['tests_count'] == 43 and source['tests_passed'] is True
         and sha(D/'tests.log') == source['tests_sha256'], 'test_binding')
    need(sha(D/'TEST_TOOLCHAIN.json') == source['test_toolchain_sha256']
         and sha(D/'PREVIOUS_PREPARE.json') == source['previous_prepare_sha256'], 'prepare_binding')
    previous = read(D/'PREVIOUS_PREPARE.json')
    need(all(sha(Path(previous['path'])/n) == h for n, h in previous['files_sha256'].items()), 'old_failure_changed')
    tool = read(D/'TEST_TOOLCHAIN.json')
    need(all(sha(D/'pytest-overlay'/n) == h for n, h in tool['files_sha256'].items()), 'test_overlay_changed')
    need(sha(Path('/tmp/dispatch_partitioned_postflight_r2_20260907.py')) == source['helper_sha256'], 'supervisor_changed')
    pre = read(O/'PRE_RELEASE_REVIEW.json', True)
    need(pre['source_receipt_sha256'] == SOURCE_SHA and pre['source_files'] == 68 and pre['linux_tests'] == 43,
         'pre_review_binding')
    intent = read(D/'INTENT.json', True)
    need(intent['audit_commit'] == C and intent['training_commit'] == T
         and intent['end_epoch']-intent['start_epoch'] == 4800, 'cpu_budget_binding')
    manifests = {}
    files = {'source.json': D/'SOURCE.json', 'test_toolchain.json': D/'TEST_TOOLCHAIN.json',
             'previous_prepare.json': D/'PREVIOUS_PREPARE.json', 'audit_intent.json': D/'INTENT.json',
             'pre_release_review.json': O/'PRE_RELEASE_REVIEW.json', 'final.json': O/'FINAL.json'}
    for case in CASES:
        step = CASES.index(case)+1
        cp = ROOT/'trajectories'/case/f'checkpoint-{step}'
        need(sha(cp/'manifest.json') == auth['checkpoint_manifest_sha256'][case], 'manifest_hash')
        manifests[case] = read(cp/'manifest.json', True)
        files[f'{case}-manifest.json'] = cp/'manifest.json'
    need(len(final['actual_payload_checks']) == 4
         and [(v['case'], v['rank']) for v in final['actual_payload_checks']] == PARTS, 'four_unique_parts')
    rows = []
    for index, (case, rank) in enumerate(PARTS):
        name = f'{case}-rank{rank}'; folder = O/name; step = CASES.index(case)+1
        need({p.name for p in folder.iterdir()} == {'INTENT.json','progress.jsonl','SUCCESS.json','COMPLETE.json'}, 'part_inventory')
        part = read(folder/'SUCCESS.json', True)
        need(read(folder/'COMPLETE.json', True) == {'sha256': sha(folder/'SUCCESS.json')}
             and read(folder/'INTENT.json', True) == {'binding': binding, 'case': case, 'rank': rank}
             and part == final['actual_payload_checks'][index], 'part_complete_binding')
        result = part['payload_check']
        need(type(part['rank']) is int and part['binding'] == binding
             and result['direct_roles_verified'] == ROLES and result['gpu_initialized'] is False
             and result['live_model_shards_independently_reconstructed'] is False
             and result['parameters'] == 1720577025 and result['completed_steps'] == step
             and result['cumulative_valid_tokens'] == step*4194304, 'part_role_cursor')
        cp = ROOT/'trajectories'/case/f'checkpoint-{step}'
        observed = read(cp/f'observed_{rank}.json', True)
        need(result['direct_state_sha256'] == {role: observed['state'][role] for role in ROLES}, 'state_hash_binding')
        wanted = {f'random_states_{rank}.pkl', f'pytorch_model/zero_pp_rank_{rank}_mp_rank_00_model_states.pt',
                  f'pytorch_model/bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt'}
        need(set(part['input_fingerprints']) == wanted, 'payload_file_coverage')
        for n, fp in part['input_fingerprints'].items():
            need(shape(cp/n, True) == fp and fp['bytes'] == manifests[case]['files'][n]['bytes'], 'payload_metadata_drift')
        progress = [json.loads(line, object_pairs_hook=unique) for line in raw(folder/'progress.jsonl', True).splitlines()]
        check_progress(progress)
        for filename in ('INTENT.json','SUCCESS.json','COMPLETE.json','progress.jsonl'):
            files[f'{name}/{filename}'] = folder/filename
        files[f'{name}/observed.json'] = cp/f'observed_{rank}.json'
        last = 0.0
        row = dict(stage=name, case=case, rank=rank, audit_commit=C, training_commit=T, new_gpu_seconds=0)
        for event in progress:
            row[event['phase']+'_seconds'] = event['elapsed_seconds']-last
            last = event['elapsed_seconds']
        rows.append(row)
    for name in [f'{c}-rank{r}' for c, r in PARTS]+['final']:
        start = read(O/(name+'-START.json'), True); done = read(O/(name+'-EXIT.json'), True)
        check_exit(done, name)
        need(start['stage'] == name and start['audit_commit'] == C and start['limit_seconds'] == 900, 'start_binding')
        started = datetime.datetime.fromisoformat(start['utc']).timestamp()
        need(intent['start_epoch'] <= started and started+done['elapsed_seconds'] <= intent['end_epoch'], 'whole_cpu_budget')
        need(sha(O/(name+'-stdout.log')) == done['stdout_sha256'], 'stdout_hash')
        scan_trace(O/(name+'-filetrace.log'), done)
        files[name+'-START.json'] = O/(name+'-START.json'); files[name+'-EXIT.json'] = O/(name+'-EXIT.json')
        row = next((v for v in rows if v['stage'] == name), None)
        if row is None:
            row = dict(stage=name, case='', rank='', audit_commit=C, training_commit=T, new_gpu_seconds=0); rows.append(row)
        row['wall_seconds'] = done['elapsed_seconds']; row['returncode'] = done['returncode']
    proof = dict(classification='INDEPENDENT_RECEIPT_COVERAGE_HASH_BINDING_AND_TRACE_REVIEW_NOT_TENSOR_REIMPLEMENTATION',
                 audit_commit=C, training_commit=T, final_sha256=sha(O/'FINAL.json'), source_sha256=SOURCE_SHA,
                 source_files=68, real_linux_tests=43, unique_parts=4, completed_stages=5,
                 checkpoint_bytes_rehashed_by_this_review=0, tensor_deserializations_by_this_review=0,
                 payload_metadata_checked=True, trace_security_recomputed=True, source_admission=False,
                 model_effect_measured=False, full_size_uninterrupted_final_parity_measured=False,
                 original_timeout_and_prepare_failure_preserved=True, new_gpu_jobs=0,
                 helper_sha256=sha(Path(__file__).resolve()), utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    os.umask(0o077); E.mkdir()
    def save(n, data):
        need(not SECRET.search(data), 'export_credential')
        p = E/n; p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        p.chmod(0o400)
    for name, p in files.items():
        data = raw(p); save(name, data); need(raw(p) == data, 'export_source_drift')
    save('independent_review.json', json.dumps(proof, sort_keys=True, indent=2, allow_nan=False).encode())
    stream = io.StringIO(newline=''); fields = sorted({k for row in rows for k in row})
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
    save('runs.csv', stream.getvalue().encode())
    listing = {p.relative_to(E).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
               for p in E.rglob('*') if p.is_file()}
    save('export_manifest.json', json.dumps({'audit_commit': C, 'files': listing}, sort_keys=True, indent=2).encode())
    print(json.dumps({'status':'INDEPENDENT_RECEIPT_REVIEW_AND_SAFE_EXPORT_PASS', 'files':len(listing),
                      'final_sha256':proof['final_sha256'], 'review_sha256':sha(E/'independent_review.json'),
                      'export_manifest_sha256':sha(E/'export_manifest.json'), 'runs':rows}, sort_keys=True))


class Checks(unittest.TestCase):
    def test_valid_exit(self):
        check_exit(dict(stage='x', returncode=0, timed_out=False, trace_security_passed=True, elapsed_seconds=1), 'x')
    def test_bad_exits(self):
        for key, value in [('returncode',False),('returncode',1),('timed_out',True),('trace_security_passed',False),('elapsed_seconds',float('nan')),('elapsed_seconds',921),('stage','y')]:
            row=dict(stage='x',returncode=0,timed_out=False,trace_security_passed=True,elapsed_seconds=1);row[key]=value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): check_exit(row,'x')
    def test_duplicate_json(self):
        with self.assertRaises(ValueError): json.loads('{"a":1,"a":2}', object_pairs_hook=unique)
    def test_valid_progress(self):
        check_progress([dict(phase=p,elapsed_seconds=i,utc=f'2026-09-07T09:00:0{i}+00:00') for i,p in enumerate(PHASES)])
    def test_missing_phase(self):
        with self.assertRaises(ValueError): check_progress([])
    def test_nonmonotonic_progress(self):
        rows=[dict(phase=p,elapsed_seconds=10-i,utc=f'2026-09-07T09:00:0{i}+00:00') for i,p in enumerate(PHASES)]
        with self.assertRaises(ValueError): check_progress(rows)


if __name__ == '__main__':
    need(sys.argv[1:] in (['--self-test'], ['--review']), 'explicit_mode_required')
    if sys.argv[1] == '--self-test': unittest.main(argv=[sys.argv[0]])
    else:
        signal.alarm(180)
        review()
        signal.alarm(0)
