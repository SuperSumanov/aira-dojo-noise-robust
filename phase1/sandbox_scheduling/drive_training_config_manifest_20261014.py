"""Bounded remote-only archive name inventory, no training rows or extraction."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import sys
import tarfile
import time
from urllib.parse import urlparse

SECRET = re.compile(r'(?i)sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|bearer\s+\S{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----')
FID = '1bdNU0JCoDvd3TUy1e6zzCPAydHdiUAsN'
CAP = 256 * 1024**2


class LimitReached(Exception):
    pass


class Bounded:
    def __init__(self, stream):
        self.stream, self.n, self.h = stream, 0, hashlib.sha256()
        self.started = time.monotonic()

    def read(self, n=-1):
        if time.monotonic() - self.started > 150 or self.n >= CAP:
            raise LimitReached('bounded_stop')
        raw = self.stream.read(min(n if n >= 0 else 65536, CAP-self.n))
        self.n += len(raw)
        self.h.update(raw)
        return raw


def names(stream):
    result, expanded = [], 0
    try:
        with tarfile.open(fileobj=stream, mode='r|gz') as archive:
            for member in archive:
                p = PurePosixPath(member.name)
                if (p.is_absolute() or '..' in p.parts or SECRET.search(member.name)
                        or member.issym() or member.islnk() or not (member.isdir() or member.isfile())):
                    raise ValueError('unsafe_metadata_no_content_export')
                if len(result) >= 1000:
                    raise ValueError('member_count_bound')
                expanded += member.size
                result.append(dict(name=member.name, bytes=member.size, directory=member.isdir()))
                if member.name == 'thinking/conversion_report.json':
                    if not member.isfile() or member.size > 65536:
                        raise ValueError('report_bound')
                    raw = archive.extractfile(member).read(65537)
                    text = raw.decode('utf-8')
                    hits = len(SECRET.findall(text))
                    result[-1].update(sha256=hashlib.sha256(raw).hexdigest(), credential_shape_hits=hits)
                    if hits:
                        result[-1]['report_not_exported'] = True
                    else:
                        cfg = json.loads(text)
                        assert isinstance(cfg, dict)
                        result[-1]['top_level_fields'] = sorted(cfg)
                        allow = {'model_path', 'tokenizer', 'tokenizer_name', 'tokenizer_path',
                                 'max_length', 'enable_thinking', 'seed', 'git_commit', 'source_commit',
                                 'loss_agg_mode', 'sampler', 'normalization', 'dtype'}
                        result[-1]['configuration_only'] = {k:v for k,v in cfg.items() if k in allow
                            and isinstance(v, (str, int, float, bool, type(None)))}
                if expanded > 512*1024**2:
                    return result, False, 'expansion_bound'
    except LimitReached:
        return result, False, 'network_or_time_bound'
    return result, True, 'tar_end_reached'


def main():
    import requests
    session = requests.Session()
    session.trust_env = False
    session.proxies = {'http':'http://137.189.90.241:8000/', 'https':'http://137.189.90.241:8000/'}
    with session.get('https://drive.usercontent.google.com/download',
                     params=dict(id=FID, export='download', confirm='t'),
                     stream=True, timeout=(15, 30)) as response:
        response.raise_for_status()
        host = urlparse(response.url).hostname or ''
        if not(host.endswith('.google.com') or host.endswith('.googleusercontent.com')):
            raise ValueError('redirect_domain')
        if 'text/html' in response.headers.get('content-type', ''):
            raise ValueError('interstitial')
        reader = Bounded(response.raw)
        entries, complete, reason = names(reader)
        result = dict(utc=datetime.now(timezone.utc).isoformat(), file_id=FID,
                      entries=entries, tar_end_reached=complete, reason=reason,
                      network_bytes=reader.n, transferred_prefix_sha256=reader.h.hexdigest(),
                      full_archive_digest_attested=False, archive_saved=False,
                      training_rows_parsed=0, archive_members_written=0,
                      script_sha256=hashlib.sha256(open(__file__, 'rb').read()).hexdigest())
        encoded = json.dumps(result)
        if SECRET.search(encoded):
            raise ValueError('export_guard')
        print(encoded)


def test():
    def fixture(name):
        out=io.BytesIO()
        with tarfile.open(fileobj=out, mode='w:gz') as t:
            m=tarfile.TarInfo(name); m.size=4
            t.addfile(m, io.BytesIO(b'xxxx'))
        out.seek(0)
        return out
    entries, done, _ = names(fixture('config.yaml'))
    assert done and entries[0]['bytes'] == 4
    for unsafe in ('../config.yaml', '/config.yaml'):
        try: names(fixture(unsafe))
        except ValueError: pass
        else: raise AssertionError('unsafe accepted')
    print(json.dumps(dict(cpu_cases=3, passed=True)))


if __name__ == '__main__':
    try:
        test() if sys.argv[1:] == ['--test'] else main()
    except Exception as exc:
        print(json.dumps(dict(status='UNRESOLVED', error_type=type(exc).__name__, contents_exported=False)))
        raise SystemExit(2)
