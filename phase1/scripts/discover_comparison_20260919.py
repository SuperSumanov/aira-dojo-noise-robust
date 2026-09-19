"""Bounded credential-first discovery. Metadata only; no archives or models."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

BASE = Path('/research/d7/spc/yzyang4')
REPO = BASE / 'aira-dojo'
PARENT = BASE / 'senior-drive-metadata-root-20260905/private_inventory.json'
PARENT_SHA = 'b6b4d0bcf1530840122dda9343b7ed54adfb30b2ac28d52ebcb3703b236b3099'
SECRET = re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
SENSITIVE = re.compile(r'(?i)(api[_ -]?key|access[_ -]?token|auth[_ -]?token|bearer|password|credential|wandb|[?&](token|key|secret)=)')

def safe_text(text):
    return '\n'.join('[REDACTED_CREDENTIAL_LINE]' if SENSITIVE.search(line) else
                     SECRET.sub('[REDACTED_SECRET]', line) for line in text.splitlines())

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], stderr=subprocess.PIPE, timeout=45).decode()

def main():
    import requests
    os.umask(0o077)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('deadline')))
    signal.alarm(300)
    out = Path(tempfile.mkdtemp(prefix='comparison-discovery-20260919-', dir=BASE))
    print(json.dumps({'output': str(out)}), flush=True)
    summary = {'utc': datetime.now(timezone.utc).isoformat(), 'output': str(out)}
    command = 'source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1; git -C /research/d7/spc/yzyang4/aira-dojo fetch --quiet --no-tags fork dojo-reproduce'
    fetch = subprocess.run(['bash', '-c', command], capture_output=True, timeout=65) if '--metadata-only' not in sys.argv else subprocess.CompletedProcess([], 99)
    summary['fetch_rc'] = fetch.returncode
    if fetch.returncode == 0:
        head = git('rev-parse', 'refs/remotes/fork/dojo-reproduce').strip()
        summary['senior_head'] = head
        paths = git('diff', '--name-only', 'aae6f7d685b09cacdc5a3d1992dd81b9eeaa7ad8', head).splitlines()
        summary['changed_files'] = len(paths)
        selected = [p for p in paths if p.startswith('src/mle_critic/docs/') and p.endswith('.md')]
        summary['changed_docs'] = selected
        docs = []
        for path in selected[:12]:
            size = int(git('cat-file', '-s', head + ':' + path))
            if size > 250000:
                docs.append({'path': path, 'status': 'TOO_LARGE_NOT_READ'}); continue
            raw = git('show', head + ':' + path)
            docs.append({'path': path, 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                         'credential_hits': len(SECRET.findall(raw)), 'redacted_text': safe_text(raw)})
        (out/'docs.redacted.json').write_text(json.dumps(docs, ensure_ascii=False, indent=2))
        print(json.dumps({'git': summary, 'docs': [{k:v for k,v in d.items() if k != 'redacted_text'} for d in docs]}, ensure_ascii=False), flush=True)
    # Reuse the previously verified complete-listing parser; it only parses supplied HTML.
    parser_path = REPO/'phase1/scripts/inspect_senior_complete_root_20260912.py'
    if not parser_path.is_file():
        parser_path = BASE/'inspect_senior_complete_root_20260912.py'
    spec = importlib.util.spec_from_file_location('listing_parser', parser_path)
    parser = importlib.util.module_from_spec(spec); spec.loader.exec_module(parser)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA or SECRET.search(raw.decode()):
        raise ValueError('parent inventory changed')
    parent = json.loads(raw)
    session = requests.Session(); session.trust_env = False
    session.proxies = {'http': 'http://137.189.90.241:8000/', 'https': 'http://137.189.90.241:8000/'}
    request_count = 0
    def listing(fid):
        nonlocal request_count
        if not re.fullmatch('[A-Za-z0-9_-]{25,80}', fid) or request_count >= 14:
            raise ValueError('request scope')
        request_count += 1
        with session.get('https://drive.google.com/embeddedfolderview', params={'id': fid}, stream=True,
                         allow_redirects=False, timeout=(10,30)) as response:
            if response.status_code != 200: raise ValueError('listing HTTP status')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 8*1024**2: raise ValueError('metadata cap')
        html = data.decode()
        try:
            return parser.embedded_items(html)
        except ValueError:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            links = [(a.get('href',''), a.get_text(strip=True)) for a in soup.find_all('a', href=True)]
            matches = [(u,n) for u,n in links if re.search(r'drive/folders/|/file/d/', u)]
            print(json.dumps({'listing_diagnostic': {'bytes': len(data), 'title': safe_text(soup.title.get_text() if soup.title else ''),
                'anchors': len(links), 'matching_anchors': len(matches), 'unique_matches': len(set(matches)),
                'visible_text': safe_text(soup.get_text(' ', strip=True))[:600],
                'matched_examples': [(safe_text(u),safe_text(n)) for u,n in matches[:2]]}}), flush=True)
            raise
    first = listing(parent['root_id']); second = listing(parent['root_id'])
    if first != second: raise ValueError('unstable root')
    folders = [x for x in first if x[1] == 'comparison' and x[2] == parser.FOLDER]
    inventory = {'utc': summary['utc'], 'root_id': parent['root_id'], 'root_entries': first, 'folders': []}
    summary['root_entries'] = len(first)
    summary['recent_folders'] = sorted(x[1] for x in first if x[2] == parser.FOLDER and x[1] >= '0910')
    summary['comparison_found'] = len(folders) == 1
    if len(folders) > 1: raise ValueError('ambiguous comparison folder')
    if folders:
        fid, name, _ = folders[0]
        children = listing(fid)
        if children != listing(fid): raise ValueError('unstable comparison')
        inventory['folders'].append({'relative': name, 'id': fid, 'entries': children})
        print(json.dumps({'comparison_entries': [(n,k) for _,n,k in children]}, ensure_ascii=False), flush=True)
        for cid, cname, kind in children:
            if kind == parser.FOLDER:
                try:
                    sub = listing(cid)
                    inventory['folders'].append({'relative': name+'/'+cname, 'id': cid, 'entries': sub})
                except ValueError:
                    inventory['folders'].append({'relative': name+'/'+cname, 'id': cid, 'entries': [], 'listing_unresolved': True})
    encoded = json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2).encode()
    if SECRET.search(encoded.decode()): raise ValueError('credential-shaped metadata')
    (out/'inventory.private.json').write_bytes(encoded)
    summary['inventory_sha256'] = hashlib.sha256(encoded).hexdigest()
    summary['folders'] = [{'relative': x['relative'], 'listing_unresolved': x.get('listing_unresolved',False), 'entries': [(n,k) for _,n,k in x['entries']]} for x in inventory['folders']]
    summary.update(requests=request_count, archives_downloaded=0, protected_outcomes_read=False, gpu_jobs=0)
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'error_type': type(exc).__name__, 'safe_reason': safe_text(str(exc))[:180]}), flush=True)
        raise SystemExit(2)
