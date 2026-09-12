"""Bounded metadata-only check of the legacy Drive 50-entry blind spot.

Endpoint verified against gdown v6.0.0 download_folder.py. No runtime upgrade,
archive downloads, credentials, recursive traversal, or corpus admission.
Two stable listings are evidence of observed consistency, not an attestation
that Google has indexed every upload.
"""
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse

BASE = Path('/research/d7/spc/yzyang4')
PARENT = BASE/'senior-root-metadata-20260912-nr5ioaoh/inventory.private.json'
PARENT_SHA = '379259f9dadecb27adb49e744bd83e6d4f21c389698208a3ef00cb2e05a98254'
LEGACY_PARSER_SHA = 'ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143'
FOLDER = 'application/vnd.google-apps.folder'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def embedded_items(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    if soup.title is None or not soup.title.get_text(strip=True):
        raise ValueError('missing listing title')
    items = []
    for link in soup.find_all('a', href=True):
        url = urlparse(link['href'])
        if url.scheme != 'https' or url.netloc != 'drive.google.com':
            continue
        folder = re.fullmatch(r'/drive/folders/([A-Za-z0-9_-]{25,80})/?', url.path)
        archive = re.fullmatch(r'/file/d/([A-Za-z0-9_-]{25,80})/view', url.path)
        if not folder and not archive:
            continue
        name = link.get_text(strip=True)
        if not name or len(name) > 512:
            raise ValueError('invalid metadata name')
        items.append(((folder or archive).group(1), name, FOLDER if folder else 'file'))
    if not items or len(items) > 2000 or len({i[0] for i in items}) != len(items):
        raise ValueError('empty, excessive or duplicate listing')
    if SECRET.search(json.dumps(items).encode()):
        raise ValueError('credential-shaped metadata')
    return sorted(items)


def comparable(items):
    return {i[0]: (i[1], i[2] == FOLDER) for i in items}


def validate(a, b, legacy):
    first, second, old = comparable(a), comparable(b), comparable(legacy)
    if len(first) != len(a) or len(second) != len(b) or len(old) != len(legacy):
        raise ValueError('duplicate identity')
    if first != second:
        raise ValueError('unstable embedded listings')
    if any(first.get(k) != v for k, v in old.items()):
        raise ValueError('legacy item absent or changed')
    return set(first) - set(old)


def main():
    import requests
    os.umask(0o077)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA or SECRET.search(raw):
        raise ValueError('parent metadata changed or unsafe')
    parent = json.loads(raw)
    folder_id = parent['root_id']
    if not re.fullmatch('[A-Za-z0-9_-]{25,80}', folder_id):
        raise ValueError('invalid root scope')
    legacy_parser = importlib.import_module('gdown.download_folder')
    if hashlib.sha256(Path(legacy_parser.__file__).read_bytes()).hexdigest() != LEGACY_PARSER_SHA:
        raise ValueError('legacy parser changed')
    session = requests.Session()
    session.trust_env = False
    session.proxies = dict(http='http://137.189.90.241:8000/', https='http://137.189.90.241:8000/')
    request_count = 0

    def get(url, params):
        nonlocal request_count
        request_count += 1
        if request_count > 3:
            raise ValueError('request cap')
        with session.get(url, params=params, stream=True, allow_redirects=False, timeout=(10, 30)) as response:
            if response.status_code != 200:
                raise ValueError('listing HTTP status')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 8*1024**2:
                    raise ValueError('listing byte cap')
        return data.decode('utf-8')

    standard_url = 'https://drive.google.com/drive/folders/' + folder_id
    first = embedded_items(get('https://drive.google.com/embeddedfolderview', {'id': folder_id}))
    _, legacy = legacy_parser._parse_google_drive_file(standard_url, get(standard_url, {'hl': 'en'}))
    second = embedded_items(get('https://drive.google.com/embeddedfolderview', {'id': folder_id}))
    additions = validate(first, second, legacy)
    validate(first, second, parent['children'])
    output = Path(tempfile.mkdtemp(prefix='senior-complete-root-20260912-', dir=BASE))
    os.chmod(output, 0o700)
    utc = datetime.now(timezone.utc).isoformat()
    private = dict(utc=utc, root_id=folder_id, entries=first, legacy=legacy)
    encoded = (json.dumps(private, sort_keys=True, indent=2)+'\n').encode()
    with (output/'inventory.private.json').open('xb') as stream:
        stream.write(encoded)
    os.chmod(output/'inventory.private.json', 0o400)
    dates = [i[1] for i in first if i[2] == FOLDER and re.fullmatch(r'09[0-3][0-9]', i[1])]
    new_dates = [i[1] for i in first if i[0] in additions and i[2] == FOLDER and re.fullmatch(r'09[0-3][0-9]', i[1])]
    public = dict(utc=utc, output=str(output), legacy_entries=len(legacy), embedded_entries=len(first),
        additional_entries=len(additions), september_directories=sorted(dates),
        additional_september_directories=sorted(new_dates), repeated_listing_equal=True,
        legacy_inclusion_passed=True, prior_listing_inclusion_passed=True, requests=request_count,
        private_inventory_sha256=hashlib.sha256(encoded).hexdigest(),
        archives_downloaded=0, archive_contents_opened=False, production_or_latest_changed=False,
        complete_index_attested=False, source='https://github.com/wkentaro/gdown/blob/v6.0.0/gdown/download_folder.py')
    with (output/'summary.json').open('x') as stream:
        json.dump(public, stream, indent=2)
    print(json.dumps(public))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(status='METADATA_FAILED_CLOSED', error_type=type(exc).__name__)))
        raise SystemExit(2)
