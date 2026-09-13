"""Actual-source memory contrast integration, never GPU/API dispatch."""
from pathlib import Path
import subprocess
import sys
from forets_environment_build_20260912 import read

def run(root):
    root=root.resolve(strict=True);artifact=read(root/'artifact.json')
    if artifact['modified_files']!=['src/dojo/core/solvers/llm_helpers/backends/paid_budget.py']:
        raise ValueError('only paid ledger identity may change source')
    from verify_forets_wallclock_20260912 import run as verify
    verify(root,blocks=(1,2))
    for name in ('verify_memory_action_hook_20260913.py','verify_memory_batch_20260913.py','verify_memory_prompt_integration_20260913.py'):
        subprocess.run([sys.executable,str(Path(__file__).with_name(name)),str(root)],check=True)

if __name__=='__main__':run(Path(sys.argv[1]))
