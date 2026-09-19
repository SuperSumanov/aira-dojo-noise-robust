"""Read-only source/config metadata and closed third-prefix error diagnosis."""
import ast,hashlib,json,re,tarfile
from pathlib import Path,PurePosixPath
BASE=Path('/research/d7/spc/yzyang4')
ASSETS=BASE/'local-qwen27b-20260914-zcx1k1dy'
ROOT=BASE/'comparison-third-bank-20260919-7b544kbs'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})')
def checked(path):
    raw=path.read_bytes()
    if path.is_symlink() or SECRET.search(raw):raise ValueError('identity/security')
    return raw
def sha(raw):return hashlib.sha256(raw).hexdigest()
out={'files':[]}
for relative in ('src/dojo/solvers/mcts/mcts.py','src/dojo/solvers/fore_ts/fore_ts.py','src/dojo/core/interpreters/fresh_container.py'):
    path=ASSETS/'source'/relative;row=dict(path=relative,exists=path.exists())
    if path.exists():
        raw=checked(path);row.update(sha256=sha(raw),classes=[n.name for n in ast.parse(raw).body if isinstance(n,ast.ClassDef)])
    out['files'].append(row)
summary_raw=checked(ROOT/'summary.json')
if sha(summary_raw)!='7dd466d42627e642ded6cd34af5660e0d0f6f76ed1150fb423565e13f7fb9371':raise ValueError('closed summary')
p=json.loads(checked(ROOT/'prepared.json'));row,=[r for r in p['rows'] if r['role']=='prefix']
raw=checked(ROOT/f'output-{row["index"]}.private.log');text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',raw.decode())
expected=p['extension_context']['historical_prefix_error']
errors=re.findall(r'(?m)^\s*((?:\w+Error|Exception):[^\n]*)',text)
core=re.sub(r'\s+Execution time:.*$','',errors[-1].strip()) if errors else None
out['prefix']=dict(log_sha256=sha(raw),historical_error=expected[:500],fresh_core_error=core[:500] if core else None,
                   exact_original_gate=text.rstrip().endswith(expected),same_core=core==expected,summary_sha256=sha(summary_raw))
wanted={'3277c81be72a1c30','58d3914785a2cfe1'};out['solver_bounds']=[]
with tarfile.open(BASE/'comparison-quarantine-20260919-_tda9fh6/archives/spooky-author-identification.tar.gz','r|gz') as archive:
    for member in archive:
        path=PurePosixPath(member.name)
        if not member.isfile() or path.name!='dojo_config.json' or sha(str(path.parent).encode())[:16] not in wanted:continue
        raw=archive.extractfile(member).read()
        if SECRET.search(raw):raise ValueError('config credential')
        cfg=json.loads(raw)['solver']
        out['solver_bounds'].append(dict(run=sha(str(path.parent).encode())[:16],config_sha256=sha(raw),
            fields={k:cfg.get(k) for k in ('step_limit','max_debug_depth','max_debug_time','time_limit_secs','execution_timeout','use_test_score')},
            operator_keys={k:sorted(v) for k,v in cfg['operators'].items()}))
encoded=json.dumps(out,indent=2)
if SECRET.search(encoded.encode()):raise ValueError('unsafe output')
print(encoded)
