"""Read-only timeout-phase evidence from the exact closed trial, no retry."""
import ast
import hashlib
import json
from pathlib import Path
import re

R = Path('/research/d7/spc/yzyang4/diagnostic-information-20261004-v1')
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+\S{12,})')

def safe(path):
    raw = path.read_bytes()
    assert not SECRET.search(raw), 'credential shape; no content emitted'
    return raw

assert (R/'all-closed.json').exists()
assert json.loads(safe(R/'closed.json'))['service_closed']
for name, cls, method in (
    ('jupyter_code_executor.py', 'JupyterCodeExecutor', 'execute_code'),
    ('jupyter_interpreter.py', 'JupyterInterpreter', 'run')):
    path = R/'source/src/dojo/core/interpreters/jupyter'/name
    raw = safe(path)
    src = raw.decode()
    tree = ast.parse(src)
    c = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    f = next(n for n in c.body if isinstance(n, ast.FunctionDef) and n.name == method)
    print(json.dumps(dict(file=name, sha256=hashlib.sha256(raw).hexdigest(),
                         method=ast.get_source_segment(src, f))))
for index, step in ((3,1), (7,2), (11,0)):
    path = R/f'episode-{index}/action-{step}/node.private.json'
    node = json.loads(safe(path))
    lines = [line for line in node['terminal'].splitlines()
             if any(s in line for s in ('Kernel did not become ready', 'Timeout', 'time limit', 'Execution time:'))]
    print(json.dumps(dict(index=index, step=step, lines=lines,
                         node_sha256=hashlib.sha256(safe(path)).hexdigest())))
