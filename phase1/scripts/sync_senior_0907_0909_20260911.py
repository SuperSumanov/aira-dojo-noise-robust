"""Fetch eight discovered archives into quarantine; never extract or promote.

0909/mcts is deliberately NOT flattened into the existing production source root.
The immutable remote inventory is metadata only, not corpus admission.
"""
import datetime as dt
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import sys
import time

from phase1.scripts.sync_senior_0906_bounded_20260908 import (
    DOWNLOAD_SHA, FOLDER_SHA, allowed_request, require, sha,
)

BASE = Path('/research/d7/spc/yzyang4')
DISCOVERY = BASE / 'senior-discovery-20260911-bye8978l'
MANIFEST = DISCOVERY / 'inventory.private.json'
MANIFEST_SHA = 'dd10aa4b2463d851d5a12184595af5f3681880894d483392ae6ffbaca711266d'
OUT = BASE / 'senior-quarantine-20260911-v1'
EXPECTED_LATEST = '1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f'
GROUPS = {'0907': 2, '0909/mcts': 6}
FILE_CAP = 128 * 1024**2
TOTAL_CAP = 1024**3
SECONDS_CAP = 1200
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{12,}|-----BEGIN .*PRIVATE KEY-----)')


def validate_inventory(value):
    folders = value['folders']
    require(len(folders) == 3 and {x['relative'] for x in folders} == {'0907', '0909', '0909/mcts'}, 'folder_scope')
    require(not SECRET.search(json.dumps(value).encode()), 'credential_shaped_metadata')
    group_map = {x['relative']: x for x in folders}
    parent = group_map['0909']['entries']
    require(len(parent) == 1 and parent[0][1:] == ['mcts', 'application/vnd.google-apps.folder'], 'parent_scope')
    require(parent[0][0] == group_map['0909/mcts']['folder_id'], 'parent_binding')
    seen = set()
    for rel, count in GROUPS.items():
        group = group_map[rel]
        require(re.fullmatch('[A-Za-z0-9_-]{10,80}', group['folder_id']), 'folder_id')
        require(len(group['entries']) == count, 'archive_count')
        names = set()
        for fid, name, kind in group['entries']:
            require(re.fullmatch('[A-Za-z0-9_-]{10,80}', fid) and fid not in seen, 'duplicate_or_invalid_id')
            require(PurePosixPath(name).name == name and '\\' not in name and name.endswith('.tar.gz')
                    and not any(ord(c) < 32 for c in name) and name not in names, 'unsafe_or_duplicate_name')
            require(kind != 'application/vnd.google-apps.folder', 'nested_folder')
            seen.add(fid); names.add(name)
    return [group_map[rel] for rel in GROUPS]


class BoundedWriter:
    def __init__(self, file, budget):
        self.file, self.budget, self.n = file, budget, 0
        self.digest = hashlib.sha256()

    def write(self, chunk):
        require(self.n + len(chunk) <= FILE_CAP and self.budget['bytes'] + len(chunk) <= TOTAL_CAP,
                'download_byte_limit')
        n = self.file.write(chunk)
        require(n == len(chunk), 'short_write')
        self.n += n; self.budget['bytes'] += n; self.digest.update(chunk)
        return n


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, sort_keys=True, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())


def expired(*_):
    raise RuntimeError('operation_time_limit')


def main():
    os.umask(0o077)
    signal.signal(signal.SIGALRM, expired); signal.alarm(SECONDS_CAP)
    require(MANIFEST.resolve() == MANIFEST and sha(MANIFEST) == MANIFEST_SHA, 'manifest_drift')
    groups = validate_inventory(json.loads(MANIFEST.read_bytes()))
    require(BASE.resolve() == BASE and not OUT.exists(), 'output_exists_or_symlink')
    latest = BASE / 'prospective_decision_v1/LATEST'
    require(latest.read_text().strip() == EXPECTED_LATEST, 'latest_changed')
    module = Path(importlib.util.find_spec('gdown').origin).parent
    require(sha(module / 'download.py') == DOWNLOAD_SHA and sha(module / 'download_folder.py') == FOLDER_SHA,
            'gdown_source_drift')
    OUT.mkdir(mode=0o700)
    # Only this new reservation file is removed; no historical data is cleaned.
    reserve = OUT / 'own-space-reservation'
    with reserve.open('xb') as f:
        os.posix_fallocate(f.fileno(), 0, TOTAL_CAP); os.fsync(f.fileno())
        stat = os.fstat(f.fileno())
    require(reserve.resolve() == reserve and reserve.stat().st_ino == stat.st_ino
            and stat.st_uid == os.getuid() and stat.st_blocks * 512 >= TOTAL_CAP, 'space_reservation_failed')
    reserve.unlink()
    import requests, gdown
    send = requests.Session.send
    requests_count = 0
    started = time.monotonic()
    def guarded_send(session, request, **kwargs):
        nonlocal requests_count
        require(allowed_request(request.method, request.url), 'http_scope')
        require(requests_count < 80 and kwargs.get('verify', True) is True, 'http_limit_or_tls')
        requests_count += 1; kwargs['timeout'] = (10, 30)
        return send(session, request, **kwargs)
    requests.Session.send = guarded_send
    records = []; budget = {'bytes': 0}
    for group in groups:
        folder = OUT / 'archives' / group['relative']; folder.mkdir(parents=True, mode=0o700)
        for fid, name, _ in group['entries']:
            target = folder / name; before = time.time()
            with target.open('xb') as f:
                writer = BoundedWriter(f, budget)
                result = gdown.download(id=fid, output=writer, quiet=True, use_cookies=False,
                                       verify=True, resume=False, proxy='http://137.189.90.241:8000/')
                require(result is writer, 'download_result'); f.flush(); os.fsync(f.fileno())
            st = target.stat()
            with target.open('rb') as f: require(f.read(3) == b'\x1f\x8b\x08', 'not_gzip')
            digest = sha(target)
            require(3 < st.st_size == writer.n <= FILE_CAP and digest == writer.digest.hexdigest(), 'download_hash')
            require(before <= st.st_mtime <= time.time(), 'mtime_not_fresh')
            target.chmod(0o400)
            records.append({'relative': group['relative'] + '/' + name, 'drive_id': fid, 'bytes': st.st_size,
                            'sha256': digest, 'mtime_ns': st.st_mtime_ns})
            print(json.dumps({'event': 'QUARANTINED_ARCHIVE', 'ordinal': len(records), 'group': group['relative'],
                              'bytes': st.st_size, 'content_opened': False}), flush=True)
        session = requests.Session(); session.trust_env = False
        session.proxies = {'http': 'http://137.189.90.241:8000/', 'https': 'http://137.189.90.241:8000/'}
        url = 'https://drive.google.com/drive/folders/' + group['folder_id']
        response = session.get(url, params={'hl': 'en'}, allow_redirects=False)
        require(response.status_code == 200, 'relist_status')
        _, rows = importlib.import_module('gdown.download_folder')._parse_google_drive_file(url, response.text)
        require(sorted(rows) == sorted(tuple(x) for x in group['entries']), 'relist_changed')
    require(latest.read_text().strip() == EXPECTED_LATEST, 'latest_changed_after')
    # Duplicate payloads are not admitted or silently deduplicated.
    require(len({r['sha256'] for r in records}) == sum(GROUPS.values()), 'duplicate_new_payload')
    save('private_manifest.json', {'records': records, 'inventory_sha256': MANIFEST_SHA,
                                  'script_sha256': sha(Path(__file__))})
    summary = {'status': 'DOWNLOADED_QUARANTINED_NOT_INTAKE_OR_TRAINING',
               'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'groups': GROUPS,
               'archives': len(records), 'bytes': budget['bytes'], 'requests': requests_count,
               'elapsed_seconds': time.monotonic() - started, 'script_sha256': sha(Path(__file__)),
               'manifest_sha256': sha(OUT / 'private_manifest.json'), 'latest_unchanged': EXPECTED_LATEST,
               'archive_contents_opened': False, 'production_source_changed': False,
               'protected_values_read': False, 'gpu_jobs': 0, 'model_calls': 0,
               'stability_mtime_backdated': False, 'nested_mcts_kept_separate': True}
    save('summary.json', summary); print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[a-z_]+', str(exc)) else 'detail_withheld'
        result = {'status': 'QUARANTINE_FAILED_CLOSED', 'error_type': type(exc).__name__, 'reason': reason}
        if OUT.is_dir() and not (OUT / 'FAILED.json').exists(): save('FAILED.json', result)
        print(json.dumps(result), flush=True); sys.exit(1)
