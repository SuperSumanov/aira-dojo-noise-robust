"""Opt-in durable capture around ONE trusted, already-authorized grading call.

Not source admission, a sandbox, a label reader, a producer launcher, or proof
of the candidate runtime. No default Dojo path imports/calls this module.
The caller must exclude protected cohorts and keep this vault outside ALL
agent mounts. The reference receipt is recorded, not presumed authenticated.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

VERSION = 'fresh-grade-capture-v1'
MAX_SUBMISSION = 64 * 1024**2
MAX_CODE = 4 * 1024**2
MAX_SOURCES = 8 * 1024**2
MAX_RESULT = 2 * 1024**2
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


class CaptureError(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise CaptureError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(raw):
    require(not SECRET.search(raw), 'credential_shape')
    return raw


def canonical(obj):
    try:
        raw = json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError, UnicodeError):
        raise CaptureError('noncanonical_result') from None
    require(len(raw) <= MAX_RESULT, 'metadata_size_limit')
    return safe(raw)


def canonical_path(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe_path')
    return p


def stable_read(path, cap, *, may_be_absent=False):
    p = canonical_path(path)
    try:
        before = p.lstat()
    except FileNotFoundError:
        require(may_be_absent, 'source_missing')
        return None
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap, 'unsafe_file_or_size')
    with p.open('rb') as f:
        opened = os.fstat(f.fileno())
        require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'open_race')
        raw = f.read(cap + 1)
        closed = os.fstat(f.fileno())
    after = p.lstat()
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(signature(before) == signature(after) and signature(opened) == signature(closed)
            and len(raw) == before.st_size <= cap, 'file_changed_during_read')
    return safe(raw)


def publish(path, raw):
    # File publication is exclusive. COMPLETE below is the transaction commit.
    with path.open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    path.chmod(0o400)


def sync_directory(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def check_inventory(root, payload_names, markers=()):
    expected_top = {n for n in payload_names if '/' not in n} | {'sources'} | set(markers)
    require({p.name for p in root.iterdir()} == expected_top, 'archive_inventory')
    source_dir = canonical_path(root/'sources')
    require(source_dir.is_dir(), 'archive_sources_directory')
    require({p.name for p in source_dir.iterdir()} ==
            {n.split('/')[1] for n in payload_names if n.startswith('sources/')}, 'archive_source_inventory')


def verify_capture(output):
    """Read-only integrity check, NOT provenance authentication; no result values returned.

    FAILED takes precedence even if a late fsync failure left COMPLETE behind.
    Trust requires an independently retained receipt hash; the directory owner
    can rewrite a receipt and its self-hash. This is not a security sandbox.
    """
    root = canonical_path(output)
    require(not (root/'FAILED.json').exists(), 'failed_transaction')
    raw = stable_read(root/'receipt.json', MAX_RESULT)
    require(stable_read(root/'COMPLETE', 64) == digest(raw).encode(), 'receipt_hash')
    receipt = json.loads(raw)
    require(receipt['protocol'] == VERSION and receipt['grading_calls'] == 1
            and receipt['source_admission'] is False
            and receipt['agent_isolation_attested'] is False, 'receipt_schema')
    names = set(receipt['files'])
    required = {'code.py', 'intent.json', 'result.json'}
    require(required <= names and 1 <= len(names - required - {'submission.csv'}) <= 256, 'payload_schema')
    require(all(n in required | {'submission.csv'} or
                re.fullmatch(r'sources/[a-z][a-z0-9_]{0,63}\.txt', n) for n in names), 'payload_name')
    check_inventory(root, names, ('receipt.json', 'COMPLETE'))
    payload = {}
    for name in sorted(names):
        cap = (MAX_SUBMISSION if name == 'submission.csv' else MAX_CODE if name == 'code.py'
               else MAX_SOURCES if name.startswith('sources/') else MAX_RESULT)
        data = stable_read(root/name, cap)
        require(receipt['files'][name] == dict(sha256=digest(data), bytes=len(data)), 'payload_hash')
        payload[name] = data
    require(sum(len(v) for n, v in payload.items() if n.startswith('sources/')) <= MAX_SOURCES, 'source_total_size')
    intent = json.loads(payload['intent.json'])
    require(intent['protocol'] == VERSION and intent['source_admission'] is False
            and intent['execution_receipt_authenticated'] is False
            and intent['agent_isolation_attested'] is False, 'intent_schema')
    require(digest(payload['intent.json']) == receipt['intent_sha256']
            and digest(payload['result.json']) == receipt['result_sha256']
            and digest(payload['code.py']) == intent['code_sha256'], 'binding_hash')
    require(intent['submission_present'] is ('submission.csv' in payload), 'submission_presence')
    require(intent['submission_sha256'] == (digest(payload['submission.csv']) if 'submission.csv' in payload else None), 'submission_hash')
    require(intent['source_files'] == {n[8:-4]: dict(sha256=digest(v), bytes=len(v))
                                      for n, v in payload.items() if n.startswith('sources/')}, 'source_binding')
    return dict(receipt_sha256=digest(raw), payload_files=len(names), integrity_verified=True,
                source_admission=False, model_effect_measured=False)


def capture_grade(*, output, submission_path, code, binding, sources, evaluate):
    """Archive exact bytes and the unmodified return of a zero-argument call.

    Nothing is deleted or retried. Any post-call failure permanently leaves an
    incomplete transaction, and the caller must NOT call the grader again.
    No grading result is printed. Identifiers and results remain in the vault.
    File hashes describe observed source files, not all executed dependencies.
    """
    require(type(code) is bytes and 0 < len(code) <= MAX_CODE, 'code_size_or_type')
    safe(code)
    require(type(binding) is dict and set(binding) == {'run_id', 'step', 'task', 'execution_receipt_sha256'}, 'binding_schema')
    require(all(type(binding[k]) is str and 0 < len(binding[k]) <= 512 and all(ord(c) >= 32 for c in binding[k])
                for k in ('run_id', 'task')), 'binding_identity')
    require(type(binding['step']) is int and binding['step'] >= 0, 'binding_step')
    require(type(binding['execution_receipt_sha256']) is str and re.fullmatch('[0-9a-f]{64}', binding['execution_receipt_sha256']), 'receipt_reference')
    require(type(sources) is dict and 1 <= len(sources) <= 256, 'source_list_required')
    require(callable(evaluate), 'callable_required')
    root = canonical_path(output); submission = canonical_path(submission_path)
    require(not root.exists() and root.parent.is_dir(), 'new_transaction_required')
    require(not root.is_relative_to(submission.parent) and not submission.is_relative_to(root), 'vault_in_submission_workspace')
    source_bytes = {}; source_paths = {}; total = 0
    for name, value in sorted(sources.items()):
        require(type(name) is str and re.fullmatch('[a-z][a-z0-9_]{0,63}', name), 'source_name')
        p = canonical_path(value)
        require(p.suffix in ('.py', '.json') and not p.name.startswith('.env'), 'source_type')
        require(not p.is_relative_to(root) and p != submission, 'source_role_alias')
        raw = stable_read(p, MAX_SOURCES); total += len(raw)
        require(total <= MAX_SOURCES, 'source_total_size')
        source_bytes[name] = raw; source_paths[name] = p
    require(len(set(source_paths.values())) == len(source_paths), 'duplicate_source_path')
    submission_bytes = stable_read(submission, MAX_SUBMISSION, may_be_absent=True)
    intent = canonical(dict(protocol=VERSION, binding=binding, started_ns=time.time_ns(),
        code_sha256=digest(code), submission_present=submission_bytes is not None,
        submission_sha256=None if submission_bytes is None else digest(submission_bytes),
        source_files={n: dict(sha256=digest(raw), bytes=len(raw)) for n, raw in source_bytes.items()},
        execution_receipt_authenticated=False, source_admission=False, agent_isolation_attested=False))
    root.mkdir(mode=0o700)
    called = False
    try:
        payload = {'intent.json': intent, 'code.py': code}
        if submission_bytes is not None: payload['submission.csv'] = submission_bytes
        (root/'sources').mkdir(mode=0o700)
        payload.update({'sources/'+name+'.txt': raw for name, raw in source_bytes.items()})
        for name, raw in payload.items(): publish(root/name, raw)
        sync_directory(root/'sources'); sync_directory(root)
        called = True
        result = evaluate()
        result_raw = canonical(result)
        require(stable_read(submission, MAX_SUBMISSION, may_be_absent=True) == submission_bytes, 'submission_changed_during_grade')
        for name, p in source_paths.items():
            require(stable_read(p, MAX_SOURCES) == source_bytes[name], 'source_changed_during_grade')
        check_inventory(root, payload)
        for name, raw in payload.items():
            require(stable_read(root/name, len(raw)) == raw, 'archived_input_changed')
        publish(root/'result.json', result_raw)
        payload['result.json'] = result_raw
        receipt = canonical(dict(protocol=VERSION, intent_sha256=digest(intent), result_sha256=digest(result_raw),
            finished_ns=time.time_ns(), grading_calls=1,
            files={n: dict(sha256=digest(raw), bytes=len(raw)) for n, raw in payload.items()},
            classification='CAPTURED_GRADING_CALL_NOT_SOURCE_OR_RUNTIME_ADMISSION',
            original_submission_deleted=False, source_admission=False, agent_isolation_attested=False))
        publish(root/'receipt.json', receipt)
        sync_directory(root)
        publish(root/'COMPLETE', digest(receipt).encode())
        sync_directory(root)
        verify_capture(root)
        return result
    except Exception as exc:
        # Never persist exception text: graders can include private rows/keys.
        failed = canonical(dict(protocol=VERSION, grading_call_entered=called,
            error_type=type(exc).__name__, error_text_sha256=digest(str(exc).encode()),
            automatic_retry_allowed=False, source_admission=False))
        if not (root/'FAILED.json').exists(): publish(root/'FAILED.json', failed)
        sync_directory(root)
        raise CaptureError('capture_incomplete_do_not_retry') from None
