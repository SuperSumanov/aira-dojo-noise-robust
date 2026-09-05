import hashlib
from pathlib import Path
import py_compile
import subprocess
import tarfile

archive = Path('/tmp/intake_successor_b2123c3.tar')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'eb81984682a83463668a3df76415b79950daf864f1c90369a91f2cfd4b7311ea'
root = Path('/tmp/intake-successor-code-b2123c3')
assert not root.exists()
with tarfile.open(archive) as t:
    m = t.getmembers()
    assert len([x for x in m if x.isfile()]) == 3 and all(x.isfile() or x.isdir() for x in m)
    assert all(not Path(x.name).is_absolute() and '..' not in Path(x.name).parts for x in m)
    root.mkdir(); t.extractall(root, filter='data')
base = root/'phase1/scripts/foreground_intake_session_20260905.py'
shell = root/'phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh'
assert hashlib.sha256(base.read_bytes()).hexdigest() == 'd0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43'
assert hashlib.sha256(shell.read_bytes()).hexdigest() == 'f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599'
subprocess.run(['bash','-n',str(shell)],check=True)
for p in root.rglob('*.py'): py_compile.compile(str(p),doraise=True)
print('DEPLOY_SOURCE_HASH_AND_SYNTAX_PASS_NO_INTAKE_LAUNCHED')
