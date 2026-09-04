"""One foreground call of the unchanged intake, under a fixed session lease.

No sleep loop, background monitor, GPU submission, model or data-value reader.
Raw subprocess streams stay in a private remote directory, never printed.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

START = dt.datetime.fromisoformat('2026-09-04T17:53:04+00:00').timestamp()
END = START + 21600
CONTROL = Path('/research/d7/spc/yzyang4/worktrees/prospective-intake-control-b20dd268')
COMMIT = 'b20dd2682d609c0236c138c08797678cf31a2fc0'
REL = 'phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh'
ORIGINAL_SHA = 'ef6584493de0f5e14a08bde4cc9501f268e43fb04bfd889af438666b1948eead'
STATE = Path('/research/d7/spc/yzyang4/prospective_decision_v1')
SOURCE = Path('/research/d7/spc/yzyang4/external/senior_data/mle')
OUT = Path('/research/d7/spc/yzyang4/foreground-intake-session-20260905')
BASELINE = 'bc9833d834fba65adbbf174301fe968c2c12da4eb8190a8f418ece58d0219456'
LOG_SHA = 'ef5599ebddf035ffca124e101fad503cf9e46576c2890ed3c2a9a8222b65e564'
INSERT = (b'if [[ "${mode}" == --run-once ]]; then\n'
          b'  # Foreground transaction for an active session; no PID file or background loop.\n'
          b'  verify_contracts\n  runner --require-strace\n  exit 0\nfi\n\n')
ANCHOR = b'if [[ "${mode}" == --initialize ]]; then\n'
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path, cap=2_000_000):
    require(path.resolve(strict=True) == path and path.is_file() and 0 < path.stat().st_size <= cap,
            'unsafe_file')
    return path.read_bytes()


def validate_derivation(original, derived):
    require(digest(original) == ORIGINAL_SHA, 'original_monitor_drift')
    require(original.count(ANCHOR) == 1 and INSERT not in original, 'unexpected_original_dispatch')
    require(derived == original.replace(ANCHOR, INSERT + ANCHOR), 'derived_body_changed')


def summary():
    latest = regular(STATE/'LATEST', 100).decode().strip()
    require(re.fullmatch('[0-9a-f]{64}', latest), 'invalid_latest')
    raw = regular(STATE/'snapshots'/latest/'accumulator'/'summary.json')
    require(not SECRET.search(raw), 'summary_credential_shape')
    value = json.loads(raw)
    inv = value['inventory']
    counts = {k: inv[k] for k in ('all_physical_runs', 'eligible_runs', 'eligible_endpoints',
                                  'eligible_structural_pairs', 'eligible_tasks')}
    require(all(type(n) is int and n >= 0 for n in counts.values()), 'unsafe_summary_counts')
    closed = value['closure']['provided']
    require(type(closed) is bool, 'invalid_closure')
    return dict(latest=latest, summary_sha256=digest(raw), closure_provided=closed, **counts)


def main():
    import fcntl
    os.umask(0o077)
    now = time.time()
    require(START <= now < END, 'outside_session_window')
    require(OUT.resolve() == OUT and not OUT.is_symlink(), 'unsafe_session_root')
    OUT.mkdir(mode=0o700, exist_ok=True)
    with (OUT/'session.lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        prior = sorted(OUT.glob('poll-*/receipt.json'))
        require(not any(OUT.glob('poll-*/FAILED')), 'previous_call_failed')
        require(len(list(OUT.glob('poll-*'))) == len(prior), 'incomplete_previous_call')
        if prior:
            last = json.loads(regular(prior[-1]))
            require(last['returncode'] == 0, 'previous_call_failed')
            require(now - last['finished_epoch'] >= 300, 'poll_interval_not_elapsed')
            expected_latest = last['after']['latest']
        else:
            expected_latest = BASELINE
        before = summary()
        require(before['latest'] == expected_latest, 'unexpected_external_snapshot_change')
        require(regular(STATE/'continuous_intake_monitor_20260821.pid', 30).strip() == b'3884166',
                'old_monitor_pid_changed')
        require(not Path('/proc/3884166').exists(), 'old_monitor_pid_live')
        require(digest(regular(STATE/'logs'/'continuous_intake_monitor_20260821.log')) == LOG_SHA,
                'old_monitor_log_changed')
        with (STATE/'runner.lock').open('rb') as runner_lock:
            fcntl.flock(runner_lock.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        require(not list(SOURCE.rglob('*.config_v2.jsonl')), 'config_sidecar_requires_review')
        original = regular(CONTROL/REL)
        script = Path(__file__).resolve().with_name(Path(REL).name)
        derived = regular(script)
        validate_derivation(original, derived)
        require(subprocess.check_output(['git', '-C', str(CONTROL), 'rev-parse', 'HEAD']).decode().strip()
                == COMMIT, 'control_commit_changed')
        require(not subprocess.check_output(['git', '-C', str(CONTROL), 'status', '--porcelain',
                                              '--untracked-files=all']).strip(), 'control_dirty')
        syntax = subprocess.run(['bash', '-n', str(script)], capture_output=True)
        require(syntax.returncode == 0 and not syntax.stdout and not syntax.stderr, 'shell_syntax')
        target = OUT/f'poll-{len(prior):03d}'
        target.mkdir(mode=0o700)
        argv = ['bash', str(script), '--run-once', str(CONTROL), COMMIT]
        context = dict(argv=argv, started_epoch=now, end_epoch=END, before=before,
                       control_commit=COMMIT, original_monitor_sha256=digest(original),
                       entry_sha256=digest(derived), driver_sha256=digest(Path(__file__).read_bytes()))
        (target/'context.json').write_text(json.dumps(context, sort_keys=True)+'\n')
        started = time.monotonic()
        with (target/'stdout.private').open('xb') as out, (target/'stderr.private').open('xb') as err:
            run = subprocess.run(argv, stdout=out, stderr=err, check=False)
        rc = run.returncode
        elapsed = time.monotonic() - started
        streams = {name: (target/name).read_bytes() for name in ('stdout.private', 'stderr.private')}
        stream_hits = sum(bool(SECRET.search(raw)) for raw in streams.values())
        require(rc == 0 and stream_hits == 0, 'intake_failed_or_credential_shape')
        after = summary()
        require(digest(regular(STATE/'logs'/'continuous_intake_monitor_20260821.log')) == LOG_SHA,
                'old_monitor_log_changed_after_call')
        receipt = dict(context, returncode=rc, elapsed_seconds=elapsed, finished_epoch=time.time(),
                       after=after, source_archives=sum(1 for _ in SOURCE.glob('*/*.tar.gz')),
                       stream_sha256={k: digest(v) for k, v in streams.items()},
                       stream_credential_shape_hits=stream_hits, background_monitor_started=False,
                       no_gpu_api_or_model_fit=True, values_or_private_identities_emitted=False)
        (target/'receipt.json').write_text(json.dumps(receipt, sort_keys=True)+'\n')
        for path in target.iterdir():
            path.chmod(0o400)
        print(json.dumps(dict(status='FOREGROUND_INTAKE_PASS', poll=len(prior), after=after,
                              source_archives=receipt['source_archives'], returncode=rc,
                              elapsed_seconds=elapsed, receipt_sha256=digest((target/'receipt.json').read_bytes())),
                         sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # An incomplete poll directory permanently blocks the next invocation.
        reason = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[a-z_]+', str(exc)) else 'detail_withheld'
        print(json.dumps(dict(status='FOREGROUND_INTAKE_FAILED_CLOSED', error=type(exc).__name__, reason=reason)))
        sys.exit(1)
