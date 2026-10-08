"""One-shot conditional launcher; never reuse a closed batch or retry sbatch."""
import json
import os
import sys
import readiness_qualified_overlap as experiment

os.umask(0o077)
os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1')
qualification = experiment.qualification_gate()
print(json.dumps({'qualification_passed':qualification}), flush=True)
experiment.set_scope()
experiment.control.r.prepare(sys.argv[1])
experiment.control.r.check_inputs()
if experiment.qualification_gate() != qualification:
    raise ValueError('qualification changed during preparation')
experiment.control.n.submit()
