"""Two-phase deletion of one explicitly approved, regenerable public-model cache."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

TARGET = Path('/research/d7/spc/yzyang4/balanced-e2a-hf-cache-e2d587d-a1')
PARENT = Path('/research/d7/spc/yzyang4')
EXPECTED_TOP = {'e2a_hf_cache_manifest.json', 'hub', 'torch'}
TOKEN = re.compile(rb'(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_.-]{12,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,})(?![A-Za-z0-9])')
DEPENDENCY_FILES = [
    Path('/research/d7/spc/yzyang4/critic-component-g0/runtime-setup-20260903-r3/dependency_closure.json'),
    Path('/research/d7/spc/yzyang4/critic-component-g0/runtime-setup-20260903-r3/compatibility.json'),
    Path('/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b/src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh'),
    Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective/pyvenv.cfg'),
]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def within(p):
    return p == TARGET or TARGET in p.parents

def inventory():
    assert TARGET.parent == PARENT and TARGET.resolve(strict=True) == TARGET
    assert not TARGET.is_symlink() and TARGET.is_dir()
    assert {p.name for p in TARGET.iterdir()} == EXPECTED_TOP
    root_stat = TARGET.lstat()
    assert root_stat.st_uid == os.getuid()
    rows = []
    for base, dirs, files in os.walk(TARGET, followlinks=False):
        for p in [Path(base)] + [Path(base) / n for n in sorted(dirs + files) if not (Path(base) / n).is_dir() or (Path(base) / n).is_symlink()]:
            s = p.lstat()
            assert s.st_uid == os.getuid() and s.st_dev == root_stat.st_dev
            assert stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode)
            link = None
            if stat.S_ISREG(s.st_mode):
                assert s.st_nlink == 1, 'Hardlink requires separate review'
            elif stat.S_ISLNK(s.st_mode):
                link = os.readlink(p)
                assert within(p.resolve(strict=True)), 'External or dangling symlink'
            rows.append({'path': str(p.relative_to(TARGET)), 'mode': s.st_mode, 'size': s.st_size,
                         'blocks': s.st_blocks, 'inode': s.st_ino, 'device': s.st_dev,
                         'uid': s.st_uid, 'mtime_ns': s.st_mtime_ns, 'link': link})
    return sorted(rows, key=lambda r: r['path'])

def dependency_gate():
    needle = str(TARGET).encode()
    for p in DEPENDENCY_FILES:
        assert p.is_file()
        assert needle not in p.read_bytes(), 'Current G0 dependency references target'
        assert not within(p.resolve(strict=True))
    runtime = Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective')
    for base, dirs, files in os.walk(runtime, followlinks=False):
        for n in dirs + files:
            p = Path(base) / n
            if p.is_symlink():
                assert not within(p.resolve(strict=True)), 'Current runtime links to target'
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    q = subprocess.run(['squeue', '-h', '-u', str(os.getuid()), '-o', '%i'], env=env, capture_output=True, check=True)
    assert not q.stdout.strip(), 'Active Slurm jobs require dependency review'
    checked = 0
    protected_transport_processes = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            if proc.stat().st_uid != os.getuid() or int(proc.name) == os.getpid():
                continue
            comm = (proc / 'comm').read_text().strip()
            if comm in {'sshd', 'systemd', '(sd-pam)'}:
                # Host session managers/transport are non-dumpable. Their comm/UID
                # and readable command line are checked, not their protected env/maps.
                # No experiment, Python, shell, tmux or batch worker is exempted.
                assert needle not in (proc / 'cmdline').read_bytes()
                protected_transport_processes.append({'pid': int(proc.name), 'comm': comm})
                continue
            for name in ['cmdline', 'environ', 'maps']:
                try:
                    assert needle not in (proc / name).read_bytes(), 'Live process references target'
                except (FileNotFoundError, ProcessLookupError):
                    pass
            for p in [proc / 'cwd', proc / 'root'] + list((proc / 'fd').iterdir()):
                try:
                    link = os.readlink(p)
                    assert not (link == str(TARGET) or link.startswith(str(TARGET) + '/')), 'Live fd/cwd references target'
                except (FileNotFoundError, ProcessLookupError):
                    pass
            checked += 1
        except (FileNotFoundError, ProcessLookupError):
            pass
    return checked, protected_transport_processes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'delete'])
    parser.add_argument('--receipt-root')
    parser.add_argument('--receipt-sha256')
    args = parser.parse_args()
    rows = inventory()
    checked, protected_transport = dependency_gate()
    manifest_bytes = (TARGET / 'e2a_hf_cache_manifest.json').read_bytes()
    assert len(manifest_bytes) < 2_000_000 and not TOKEN.search(manifest_bytes), 'Manifest credential/size gate'
    manifest = json.loads(manifest_bytes)
    data = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()
    assert not TOKEN.search(data), 'Inventory credential gate'
    if args.mode == 'prepare':
        out = Path(tempfile.mkdtemp(prefix='approved-e2a-cache-cleanup-20260903-', dir='/tmp'))
        (out / 'inventory.json').write_bytes(data)
        (out / 'original_manifest.json').write_bytes(manifest_bytes)
        receipt = {'status': 'PREDELETE_READONLY_PASS', 'utc': now(), 'target': str(TARGET),
                   'root_inode': TARGET.stat().st_ino, 'root_device': TARGET.stat().st_dev,
                   'allocated_bytes': sum(r['blocks'] * 512 for r in rows), 'entries': len(rows),
                   'regular_files': sum(stat.S_ISREG(r['mode']) for r in rows),
                   'symlinks': sum(stat.S_ISLNK(r['mode']) for r in rows),
                   'outside_symlinks': 0, 'regular_hardlinks': 0, 'live_reference_hits': 0,
                   'same_uid_processes_checked': checked, 'active_slurm_jobs': 0,
                   'host_session_services_metadata_only_not_env_or_maps_inspected': protected_transport,
                   'current_g0_dependency_reference_hits': 0,
                   'manifest_sha256': digest(manifest_bytes), 'inventory_sha256': digest(data),
                   'manifest_top_keys': sorted(manifest) if isinstance(manifest, dict) else [],
                   'user_approved_only_this_directory': True, 'deleted': False}
        encoded = json.dumps(receipt, sort_keys=True, indent=2).encode()
        (out / 'predelete_receipt.json').write_bytes(encoded)
        print(json.dumps({'receipt_root': str(out), 'receipt_sha256': digest(encoded), **receipt}, sort_keys=True))
        return
    out = Path(args.receipt_root)
    assert out.parent == Path('/tmp') and out.name.startswith('approved-e2a-cache-cleanup-20260903-')
    assert out.resolve(strict=True) == out and not out.is_symlink()
    raw = (out / 'predelete_receipt.json').read_bytes()
    assert digest(raw) == args.receipt_sha256
    receipt = json.loads(raw)
    assert receipt['target'] == str(TARGET) and receipt['user_approved_only_this_directory']
    assert digest(data) == receipt['inventory_sha256'], 'Cache changed since review'
    assert digest(manifest_bytes) == receipt['manifest_sha256']
    assert (TARGET.stat().st_dev, TARGET.stat().st_ino) == (receipt['root_device'], receipt['root_inode'])
    assert not (out / 'deletion_intent.json').exists()
    (out / 'deletion_intent.json').write_text(json.dumps({'utc': now(), 'target': str(TARGET)}))
    # Target and all descendants have just passed owner/device/no-external-link gates.
    # Only directories need write permission for unlink; never chmod model files or symlinks.
    for row in rows:
        if stat.S_ISDIR(row['mode']):
            p = TARGET / row['path']
            assert not p.is_symlink() and within(p.resolve(strict=True))
            os.chmod(p, stat.S_IMODE(row['mode']) | stat.S_IWUSR | stat.S_IXUSR, follow_symlinks=False)
    assert shutil.rmtree.avoids_symlink_attacks
    shutil.rmtree(TARGET)
    assert not TARGET.exists() and not TARGET.is_symlink()
    result = {'status': 'APPROVED_SINGLE_CACHE_DELETED', 'utc': now(), 'target': str(TARGET),
              'prior_allocated_bytes': receipt['allocated_bytes'], 'target_absent': True,
              'raw_corpus_or_trained_checkpoint_deleted': False, 'other_directories_deleted': False,
              'predelete_receipt_sha256': digest(raw), 'manifest_sha256': digest(manifest_bytes),
              'recovery': 'Redownload public upstream artifacts using preserved exact cache manifest; no trash copy retained.'}
    (out / 'deletion_receipt.json').write_text(json.dumps(result, sort_keys=True, indent=2))
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
