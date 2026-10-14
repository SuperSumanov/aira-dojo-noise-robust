"""Remote-only intake of one outcome-unselected, explicitly shared 27B adapter.

No training or model execution. Never extract arbitrary archive paths or emit
raw text/configs. Source names and revision hints do not establish daily lineage.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import tarfile
import tempfile
import time
from urllib.parse import urlparse

ROOT = Path('/research/d7/spc/yzyang4')
DONOR = ROOT/'scheduling-long-effort-20261013-v1'
FID = '1_GXBwH5jRXTnt-lW_-ur4l0rUPBav2ZK'
CAP = 3*1024**3
SECRET = re.compile(r'(?i)(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|bearer\s+\S{12,}|BEGIN [A-Z ]*PRIVATE KEY)')
FIELDS = ('base_model_name_or_path', 'revision', 'peft_type', 'task_type', 'r',
          'lora_alpha', 'lora_dropout', 'target_modules', 'modules_to_save',
          'bias', 'use_dora', 'use_rslora', 'inference_mode')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1024**2), b''):
            h.update(data)
    return h.hexdigest()


def safe_json(raw):
    text = raw.decode('utf-8')
    if SECRET.search(text):
        raise ValueError('credential-shaped metadata')
    return json.loads(text)


def header(path):
    with Path(path).open('rb') as f:
        n = struct.unpack('<Q', f.read(8))[0]
        if not 0 < n <= 8*1024**2:
            raise ValueError('tensor header bound')
        h = safe_json(f.read(n))
    tensors = {k: v for k, v in h.items() if k != '__metadata__'}
    ranges = sorted(tuple(v['data_offsets']) for v in tensors.values())
    last = 0
    for a, b in ranges:
        if a != last or b < a:
            raise ValueError('invalid tensor offsets')
        last = b
    if last+8+n != Path(path).stat().st_size:
        raise ValueError('tensor file size')
    return tensors


def main(file_id=FID, lineage='score', date='20261014'):
    import requests
    if not re.fullmatch(r'[A-Za-z0-9_-]{25,80}', file_id) or lineage not in ('score', 'metric') or not re.fullmatch(r'20[0-9]{6}', date):
        raise ValueError('invalid explicit intake identity')
    os.umask(0o077)
    assert json.loads((DONOR/'closed.json').read_text())['complete'] == 24
    out = Path(tempfile.mkdtemp(prefix=f'weight-effort-adapter-{lineage}-{date}-', dir=ROOT))
    print(json.dumps(dict(status='STAGING', directory=str(out))), flush=True)
    free = shutil.disk_usage(ROOT).free
    if free < 8*1024**3:
        raise ValueError('filesystem reserve')
    archive = out/f'online_thinking_{lineage}_step30.tar.gz'
    part = out/'download.part'
    start = time.monotonic()
    session = requests.Session(); session.trust_env = False
    session.proxies = dict(http='http://137.189.90.241:8000/', https='http://137.189.90.241:8000/')
    total = 0
    with session.get('https://drive.usercontent.google.com/download',
                     params=dict(id=file_id, export='download', confirm='t'),
                     stream=True, timeout=(15, 45)) as res:
        res.raise_for_status()
        host = urlparse(res.url).hostname or ''
        if not (host.endswith('.google.com') or host.endswith('.googleusercontent.com')):
            raise ValueError('redirect domain')
        if 'text/html' in res.headers.get('content-type', '') or int(res.headers.get('content-length', '0')) > CAP:
            raise ValueError('interstitial or download bound')
        with part.open('xb') as f:
            for data in res.iter_content(1024**2):
                total += len(data)
                if total > CAP or time.monotonic()-start > 900:
                    raise ValueError('download bound')
                f.write(data)
    part.rename(archive)
    inventory, members, expanded = [], {}, 0
    with tarfile.open(archive, 'r:gz') as tar:
        for m in tar:
            p = PurePosixPath(m.name)
            if len(inventory) >= 100 or p.is_absolute() or '..' in p.parts or SECRET.search(m.name):
                raise ValueError('archive name bound')
            if not (m.isfile() or m.isdir()) or m.issym() or m.islnk():
                raise ValueError('archive member type')
            expanded += m.size
            if expanded > 5*1024**3:
                raise ValueError('archive expansion bound')
            inventory.append(dict(name=m.name, bytes=m.size, directory=m.isdir()))
            if p.name in ('adapter_config.json', 'adapter_model.safetensors'):
                if not m.isfile() or p.name in members:
                    raise ValueError('ambiguous adapter member')
                members[p.name] = m
        if set(members) != {'adapter_config.json', 'adapter_model.safetensors'}:
            raise ValueError('adapter files missing')
        if members['adapter_config.json'].size > 65536:
            raise ValueError('config size')
        raw = tar.extractfile(members['adapter_config.json']).read()
        cfg = safe_json(raw)
        dest = out/'accepted_adapter'; dest.mkdir()
        with (dest/'adapter_config.json').open('xb') as f: f.write(raw)
        with tar.extractfile(members['adapter_model.safetensors']) as source, (dest/'adapter_model.safetensors').open('xb') as target:
            shutil.copyfileobj(source, target, 1024**2)
    weights = dest/'adapter_model.safetensors'
    tensors = header(weights)
    import torch
    from safetensors import safe_open
    torch.set_num_threads(2)
    nonfinite, zero, elements = 0, 0, 0
    with safe_open(str(weights), framework='pt', device='cpu') as sf:
        assert set(sf.keys()) == set(tensors)
        for name in sf.keys():
            value = sf.get_tensor(name)
            elements += value.numel()
            nonfinite += int((~value.isfinite()).sum().item())
            zero += int((value == 0).all().item())
    report = dict(status='CPU_INTAKE_ONLY', utc=datetime.now(timezone.utc).isoformat(),
        file_id=file_id, declared_lineage=lineage, archive_sha256=digest(archive), archive_bytes=total,
        directory=str(out), adapter_directory=str(dest), inventory=inventory,
        config={k: cfg.get(k) for k in FIELDS}, config_sha256=digest(dest/'adapter_config.json'),
        weights_sha256=digest(weights), tensors=len(tensors), elements=elements,
        nonfinite_elements=nonfinite, all_zero_tensors=zero,
        dtype_counts=dict(Counter(v['dtype'] for v in tensors.values())),
        shapes=dict(Counter(str(v['shape']) for v in tensors.values())),
        tensor_names_first_six=sorted(tensors)[:6], elapsed_seconds=time.monotonic()-start,
        gpu_jobs=0, model_executions=0,
        limitation='One preselected shared adapter, no outcome-based checkpoint choice. CPU intake does not prove base revision, training lineage, runtime compatibility or quality.')
    if nonfinite or SECRET.search(json.dumps(report)):
        raise ValueError('tensor or export guard')
    with (out/'intake.safe.json').open('x') as f: json.dump(report, f, indent=2)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--file-id', default=FID)
        parser.add_argument('--lineage', choices=('score', 'metric'), default='score')
        parser.add_argument('--date', default='20261014')
        args = parser.parse_args()
        main(args.file_id, args.lineage, args.date)
    except Exception as exc:
        print(json.dumps(dict(status='FAILED_CLOSED', error_type=type(exc).__name__)), flush=True)
        raise SystemExit(2)
