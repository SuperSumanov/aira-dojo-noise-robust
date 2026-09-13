"""Run actual-source CPU checks before activating any budget or allocation."""
from pathlib import Path
import subprocess
import sys
from forets_environment_build_20260912 import read

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')

if __name__=='__main__':
    build=read(ROOT/'build.json')
    if build['source_tree']!='f7a8b9e3c07b530467573315d55f62203cc67895':raise ValueError('new exact package')
    from verify_forets_wallclock_20260912 import run
    run(ROOT,blocks=(1,2))
    for name in ('verify_deployed_action_hook_20260913.py','verify_uniform_delivery_batch_20260913.py'):
        subprocess.run([sys.executable,str(Path(__file__).with_name(name)),str(ROOT)],check=True)
