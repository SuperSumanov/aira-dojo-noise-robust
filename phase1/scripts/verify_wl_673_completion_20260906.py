"""Independent read-only completion check/export. No prediction deserialization.

The already frozen numerical verifier checks predictions internally. This separate
postcheck validates its committed artifact, process result, traces, hashes, immutable
files and aggregate receipt. It does not rerun scoring or claim model effectiveness.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
import time

B = Path('/research/d7/spc/yzyang4')
A = B / 'wl-catchup-session-673-20260906'
W = B / 'wl-graph-escrow-snapshot-chain'
FORMAL = W / '20260905T214440Z_cdae57a622cf'
EXPORT = Path('/tmp/wl-673-completion-20260906')
TAR = Path('/tmp/wl-673-completion-20260906.tar')
TARGET = 'cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2'
PRIOR = 'e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d'
WRAPPER_COMMIT = '4395e1800bf8350cecc0ecd6513bf0c11722d3c2'
CONTROL = B / 'worktrees/alias_monitor_bc362df_v2_nosmudge'
SCORER = B / 'worktrees/codex_wl_escrow_031edb3'
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
FORBIDDEN = re.compile(rb'(?i)/prospective_decision_v1/(?:label|outcome|scorer)|label_vault|outcome_vault|score_registry|regrade')
SHA = re.compile(r'[0-9a-f]{64}')
RECEIPT_KEYS = {'snapshot_sha256', 'artifact_summary_sha256', 'independent_verification_sha256',
                'selected_runs', 'added_runs', 'removed_runs', 'common_pairs',
                'support_gate_is_provisional_until_closure', 'outcomes_read', 'effect_metrics_computed'}
FROZEN_OTHER = {
    'transition-future-escrow/monitor_7458f09_snapshot_chain_v1/state.tsv': 'ac66b2deb9054b05e9fab803587d1ee38478f88cbadc86aebfa9f4a9f7ebad4e',
    'transition-future-escrow/monitor_7458f09_snapshot_chain_v1/monitor.log': 'a23e382f0a8ccb2684dbd29bed68ae0ea1d61c7a6a1727f03195033697f9ec43',
    'prediction-receipt-common-support/monitor_9f2cbe9_v1/state.tsv': '6a1ac64a49221f3879a165e608b3cb8298aab221f3ff1bcd20764c1fe47d38bc',
    'prediction-receipt-common-support/monitor_9f2cbe9_v1/monitor.log': '72f4fb13605a2aa6cc092f625799e671f140b39a79313a03f1f1847f70d84a22',
}


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def safe_raw(path, cap=65536):
    require(path.resolve() == path and path.is_file() and path.stat().st_size <= cap, 'safe_metadata_path')
    raw = path.read_bytes()
    require(not SECRET.search(raw), 'credential_shape_withheld')
    return raw


def safe_json(path):
    return json.loads(safe_raw(path))


def manifest_entries(raw):
    require(len(raw) < 1_000_000, 'manifest_size')
    records = {}
    for line in raw.decode('utf-8').splitlines():
        m = re.fullmatch(r'([0-9a-f]{64})  \./(.+)', line)
        require(m is not None, 'manifest_schema')
        digest, name = m.groups()
        p = PurePosixPath(name)
        require(not p.is_absolute() and p.parts and str(p) == name and
                all(v not in ('.', '..') for v in p.parts) and '\\' not in name and
                '\x00' not in name and not any(ord(c) < 32 for c in name), 'manifest_path')
        require(name not in records, 'duplicate_manifest_path')
        records[name] = digest
    require(bool(records), 'empty_manifest')
    return records


def validate_receipt(value):
    require(set(value) == RECEIPT_KEYS, 'receipt_schema')
    require(value['snapshot_sha256'] == TARGET, 'receipt_snapshot')
    for k in ('artifact_summary_sha256', 'independent_verification_sha256'):
        require(isinstance(value[k], str) and SHA.fullmatch(value[k]), 'receipt_sha')
    for k, expected in (('selected_runs', 673), ('added_runs', 156), ('removed_runs', 0)):
        require(type(value[k]) is int and value[k] == expected, 'receipt_run_count')
    require(type(value['common_pairs']) is int and value['common_pairs'] >= 0, 'common_pair_count')
    require(value['support_gate_is_provisional_until_closure'] is True and
            value['outcomes_read'] is False and value['effect_metrics_computed'] == [], 'receipt_blindness')


def scan_stream(path, trace=False):
    # Byte-level security check only; nothing is parsed or printed from predictions.
    tail = b''
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            part = tail + block
            require(not SECRET.search(part), 'credential_shape_withheld')
            require(not trace or not FORBIDDEN.search(part), 'forbidden_trace_withheld')
            tail = part[-4096:]


def verify_formal(root):
    require(root.resolve() == root and root.is_dir(), 'formal_root')
    require((root / 'COMPLETE').is_file() and not (root / 'FAILURE').exists(), 'not_complete')
    entries = manifest_entries(safe_raw(root / 'SHA256SUMS', 1_000_000))
    files = {}
    before = {}
    for path in [root, *root.rglob('*')]:
        s = path.lstat()
        require(not stat.S_ISLNK(s.st_mode) and not (s.st_mode & 0o222), 'not_read_only')
        require(stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode), 'special_file')
        before[path] = (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns)
        if path.is_file():
            require(s.st_nlink == 1 and path.resolve() == path, 'file_alias')
            files[path.relative_to(root).as_posix()] = path
    require(set(files) == set(entries) | {'SHA256SUMS', 'manifest_verification.txt'}, 'unmanifested_file')
    expected_manifest_check = ''.join('./' + name + ': OK\n' for name in entries).encode('utf-8')
    require(safe_raw(root / 'manifest_verification.txt', 1_000_000) == expected_manifest_check,
            'original_manifest_check_mismatch')
    trace_count = 0
    for name, digest in entries.items():
        path = files[name]
        require(sha(path) == digest, 'manifest_hash_mismatch')
        is_trace = '.strace' in path.name
        scan_stream(path, is_trace)
        trace_count += int(is_trace)
    require(trace_count >= 3, 'missing_stage_traces')
    for path, original in before.items():
        s = path.lstat()
        require(original == (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns), 'artifact_changed_during_check')
    return {'manifested_files_verified': len(entries), 'read_only_files_verified': len(files),
            'trace_files_scanned': trace_count, 'credential_hits': 0, 'forbidden_trace_hits': 0,
            'formal_manifest_sha256': sha(root / 'SHA256SUMS'),
            'original_manifest_check_sha256': sha(root / 'manifest_verification.txt')}


def stage_resources(root, name):
    require(safe_raw(root / (name + '.rc.txt')).strip() == b'0', 'stage_failed')
    raw = safe_raw(root / (name + '.time.txt'))
    text = raw.decode('utf-8')
    values = {}
    for label, key, cast in [('User time (seconds)', 'user_seconds', float),
                             ('System time (seconds)', 'system_seconds', float),
                             ('Maximum resident set size (kbytes)', 'peak_rss_kbytes', int)]:
        matches = re.findall(r'^\s*' + re.escape(label) + r':\s*([0-9.]+)\s*$', text, re.M)
        require(len(matches) == 1, 'resource_field_missing')
        value = cast(matches[0])
        require(math.isfinite(value) and value >= 0, 'resource_value_invalid')
        values[key] = value
    require(re.search(r'^\s*Exit status:\s*0\s*$', text, re.M) is not None, 'time_exit_nonzero')
    return dict(stage=name, returncode=0, **values)


def git_output(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=60)
    require(p.returncode == 0 and not SECRET.search(p.stdout + p.stderr), 'git_metadata_failure')
    return p.stdout


def main():
    require(not EXPORT.exists() and not TAR.exists(), 'export_already_exists')
    require(A.resolve() == A and not (A / 'failure.json').exists(), 'wrapper_failure_or_alias')
    terminal = safe_json(A / 'terminal.json')
    require(set(terminal) == {'returncode', 'elapsed_seconds'} and type(terminal['returncode']) is int and
            terminal['returncode'] == 0 and 0 < terminal['elapsed_seconds'] <= 7230, 'terminal_not_success')
    intent = safe_json(A / 'intent.json')
    wrapper = git_output(B / 'aira-dojo', 'show', WRAPPER_COMMIT + ':phase1/scripts/run_wl_catchup_673_20260906.py')
    require(intent['public_commit'] == WRAPPER_COMMIT and intent['wrapper_sha256'] == hashlib.sha256(wrapper).hexdigest(), 'wrapper_identity')
    require(intent['prior'] == PRIOR and intent['latest'] == TARGET and intent['wall_cap_seconds'] == 7200
            and intent['gpu_api_model_fit'] == 0, 'intent_scope')
    require(sha(Path('/tmp/run_wl_catchup_673_20260906.py')) == intent['wrapper_sha256'], 'wrapper_disk_drift')
    for repo, commit in [(CONTROL, 'bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0'),
                         (SCORER, '031edb34400781ca026bc9833ac7f850312ffb1c')]:
        require(git_output(repo, 'rev-parse', 'HEAD').decode().strip() == commit, 'source_head_drift')
        require(not git_output(repo, 'status', '--porcelain', '--untracked-files=all').strip(), 'source_dirty')
    for name, digest in FROZEN_OTHER.items():
        require(sha(B / name) == digest, 'other_monitor_changed')
    process = safe_json(A / 'process.json')
    require(process['pid'] == process['process_group'] == 2896379 and not (Path('/proc') / '2896379').exists(), 'original_pid_present')
    state = safe_raw(W / 'monitor_3932b38_v1/state.tsv').decode().strip().split('\t')
    require(len(state) == 4 and state[0] == TARGET and state[1] == str(FORMAL / 'artifact') and state[3] == '673', 'wrong_state_promotion')
    require(safe_raw(B / 'prospective_decision_v1/LATEST').decode().strip() == TARGET, 'latest_changed')
    verified = verify_formal(FORMAL)
    receipt = safe_json(FORMAL / 'monitor_receipt.json')
    validate_receipt(receipt)
    require(receipt['artifact_summary_sha256'] == state[2] == sha(FORMAL / 'artifact/summary.json'), 'artifact_summary_binding')
    require(receipt['independent_verification_sha256'] == sha(FORMAL / 'independent_verification.json'), 'numerical_verifier_binding')
    safe = safe_json(A / 'safe_receipt.json')
    require(safe['status'] == 'WL_COVERAGE_PROMOTED_PENDING_INDEPENDENT_POSTCHECK' and safe['artifact'] == str(FORMAL)
            and safe['manifest_sha256'] == verified['formal_manifest_sha256'] and safe['prior_runs'] == 517
            and safe['current_runs'] == 673 and safe['added_runs'] == 156 and safe['outcomes_read'] is False
            and safe['prediction_values_emitted'] is False and safe['model_fits'] == 0, 'wrapper_safe_receipt')
    require(safe_raw(FORMAL / 'security.txt').decode().strip().splitlines() ==
            ['forbidden_path_hits=0', 'credential_content_file_hits=0'], 'original_security_failure')
    resources = [stage_resources(FORMAL, name) for name in ('producer', 'independent_verifier', 'snapshot_chain')]
    report = dict(status='WL_FROZEN_COVERAGE_INDEPENDENT_POSTCHECK_PASSED', observed_epoch=time.time(),
                  verification_source_sha256=sha(Path(__file__)), wrapper_commit=WRAPPER_COMMIT,
                  snapshot_sha256=TARGET, prior_runs=517, current_runs=673, added_runs=156, removed_runs=0,
                  shared_pairs_preserved=receipt['common_pairs'], wall_seconds=terminal['elapsed_seconds'],
                  resources=resources, numerical_verifier_receipt_sha256=receipt['independent_verification_sha256'],
                  chain_receipt_sha256=sha(FORMAL / 'snapshot_chain_receipt.json'),
                  support_is_provisional=True, label_or_outcome_values_read=False, prediction_values_deserialized=False,
                  gpu_jobs=0, api_calls=0, model_fits=0, effect_metrics_computed=[], **verified)
    # Export only schema-known aggregate receipts and command-free resource projections.
    copies = [(FORMAL / name, 'formal_' + name) for name in
              ('monitor_receipt.json', 'security.txt', 'preflight13.txt', 'matrix.txt',
               'producer.rc.txt', 'independent_verifier.rc.txt', 'snapshot_chain.rc.txt')]
    copies += [(A / name, 'wrapper_' + name) for name in ('intent.json', 'storage.json', 'terminal.json', 'safe_receipt.json')]
    safe_copies = {name: safe_raw(path) for path, name in copies}
    EXPORT.mkdir(mode=0o700)
    for name, raw in safe_copies.items():
        with (EXPORT / name).open('xb') as stream:
            stream.write(raw)
    with (EXPORT / 'independent_postcheck.json').open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
    files = {p.name: sha(p) for p in sorted(EXPORT.iterdir())}
    with (EXPORT / 'manifest.json').open('x') as stream:
        json.dump(files, stream, sort_keys=True, indent=2)
    with tarfile.open(TAR, 'x') as archive:
        for p in sorted(EXPORT.iterdir()):
            archive.add(p, arcname=p.name, recursive=False)
    print(json.dumps(dict(status=report['status'], current_runs=673, added_runs=156,
                         manifest_sha256=sha(EXPORT / 'manifest.json'), export_sha256=sha(TAR),
                         export_files=len(files) + 1, formal_verified_files=verified['manifested_files_verified'],
                         wall_seconds=report['wall_seconds'], export=str(TAR)), sort_keys=True))


if __name__ == '__main__':
    os.umask(0o077)
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'WL_POSTCHECK_FAILED_CLOSED', 'reason': str(exc) if type(exc) is RuntimeError else type(exc).__name__}))
        raise SystemExit(1)
