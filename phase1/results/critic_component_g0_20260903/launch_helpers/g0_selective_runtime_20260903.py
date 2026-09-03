"""Build a task-local dependency closure using existing, unmodified packages."""
import argparse
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import subprocess
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

TARGET = Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective')
SETUP = Path('/research/d7/spc/yzyang4/critic-component-g0/runtime-setup-20260903-r3')
ALLOWED = (
    Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-overlay/lib/python3.11/site-packages'),
    Path('/research/d7/spc/yzyang4/venvs/exp/lib/python3.11/site-packages'),
)
ROOTS = ['torch==2.11.0+cu128', 'numpy==1.26.4', 'transformers==5.12.1',
         'accelerate==1.14.0', 'deepspeed==0.19.3', 'ninja==1.13.0',
         'pip==' + md.version('pip')]


def closure():
    selected, requested_extras, done = {}, {}, {}
    pending = [Requirement(r) for r in ROOTS]
    while pending:
        req = pending.pop()
        name = canonicalize_name(req.name)
        dist = md.distribution(req.name)
        if not req.specifier.contains(dist.version, prereleases=True):
            raise RuntimeError(f'Unsatisfied dependency: {req}; installed={dist.version}')
        base = Path(dist.locate_file('')).resolve()
        if base not in ALLOWED:
            raise RuntimeError(f'Unexpected package root: {name}: {base}')
        selected[name] = dist
        extras = requested_extras.setdefault(name, set())
        extras.update(req.extras)
        current = frozenset(extras)
        if done.get(name) == current:
            continue
        done[name] = current
        for raw in dist.requires or []:
            dep = Requirement(raw)
            if dep.marker is None or any(dep.marker.evaluate({'extra': e}) for e in [''] + sorted(extras)):
                pending.append(dep)
    return selected


def plan(selected):
    links, packages, scripts = {}, {}, {}
    for name, dist in sorted(selected.items()):
        base = Path(dist.locate_file('')).resolve()
        files = dist.files
        if not files:
            raise RuntimeError(f'Missing RECORD for {name}')
        record = next((f for f in files if str(f).endswith('.dist-info/RECORD')), None)
        if record is None:
            raise RuntimeError(f'Missing RECORD for {name}')
        record_path = Path(dist.locate_file(record))
        packages[name] = {'version': dist.version, 'backing_site': str(base),
                          'record_sha256': hashlib.sha256(record_path.read_bytes()).hexdigest()}
        for f in files:
            parts = f.parts
            if not parts or parts[0] == '..' or '__pycache__' in parts:
                continue
            # Namespace roots may be shared by unrelated distributions.
            width = 2 if parts[0] in {'nvidia', 'google', 'cuda'} and len(parts) > 1 else 1
            rel = Path(*parts[:width])
            src = base / rel
            if not src.exists():
                raise RuntimeError(f'Missing package path: {src}')
            if src.is_symlink():
                raise RuntimeError(f'Unexpected top-level backing symlink: {src}')
            if rel.suffix == '.pth':
                # This NVIDIA shim was inspected: only installs a cuda namespace __version__ proxy.
                lines = [line.strip() for line in src.read_text().splitlines()
                         if line.strip() and not line.lstrip().startswith('#')]
                allowed_pth = {
                    '_cuda_bindings_redirector.pth': ['import _cuda_bindings_redirector'],
                    'distutils-precedence.pth': ["import os; var = 'SETUPTOOLS_USE_DISTUTILS'; enabled = os.environ.get(var, 'local') == 'local'; enabled and __import__('_distutils_hack').add_shim();"],
                }
                if lines != allowed_pth.get(rel.name):
                    raise RuntimeError(f'Requires review of .pth file: {src}')
            prior = links.get(str(rel))
            if prior is not None and prior != str(src):
                raise RuntimeError(f'Package path collision: {rel}')
            links[str(rel)] = str(src)
        for ep in dist.entry_points:
            if ep.group == 'console_scripts':
                if ep.name in scripts and scripts[ep.name] != ep.value:
                    raise RuntimeError(f'Entry point collision: {ep.name}')
                scripts[ep.name] = ep.value
    return {'roots': ROOTS, 'packages': packages, 'links': links, 'console_scripts': scripts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assert sys.version_info[:2] == (3, 11)
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    payload = plan(closure())
    if args.apply:
        if TARGET.exists() or SETUP.exists():
            raise RuntimeError('Refusing to reuse existing task directories')
        SETUP.mkdir(mode=0o700)
        subprocess.run(['/research/d7/spc/yzyang4/venvs/exp/bin/python', '-m', 'venv', '--without-pip', str(TARGET)], check=True)
        site = TARGET / 'lib/python3.11/site-packages'
        for rel, backing in sorted(payload['links'].items()):
            dest = site / rel
            if dest.exists() or dest.is_symlink():
                raise RuntimeError(f'Existing target entry: {dest}')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(backing, target_is_directory=Path(backing).is_dir())
        for name, value in sorted(payload['console_scripts'].items()):
            if '/' in name or '\\' in name:
                raise RuntimeError('Invalid script name')
            module, attr = value.split(':', 1)
            attr = attr.split(' ', 1)[0]
            dest = TARGET / 'bin' / name
            if dest.exists():
                raise RuntimeError(f'Existing entry point: {dest}')
            dest.write_text(f'#!{TARGET}/bin/python\nimport sys\nfrom {module} import {attr}\nif __name__ == "__main__":\n    sys.exit({attr}())\n')
            dest.chmod(0o755)
        (SETUP / 'dependency_closure.json').write_text(json.dumps(payload, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': 'BUILT' if args.apply else 'PLAN_ONLY',
                      'packages': {k: v['version'] for k, v in payload['packages'].items()},
                      'package_count': len(payload['packages']), 'link_count': len(payload['links']),
                      'console_script_count': len(payload['console_scripts']),
                      'target': str(TARGET), 'parent_modified': False}, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
