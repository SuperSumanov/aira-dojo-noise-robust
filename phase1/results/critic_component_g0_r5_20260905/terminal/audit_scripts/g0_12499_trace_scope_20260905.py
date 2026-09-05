"""Conservative observed-file-open audit; NOT an OS sandbox certificate."""
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys

TRACE = Path('/research/d7/spc/yzyang4/critic-component-g0/runs/job-12499/file_access.strace')
OUT = Path(sys.argv[1])
SECRET = re.compile(r'(?i)(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})(?![A-Za-z0-9])|Bearer\s+\S+')
BLOCK = re.compile(r'(?i)first[-_]?960|target[-_]?(?:300|522)|prospective_decision|label[_-]?vault|prediction[_-]?escrow|\.env(?:$|/)|/\.ssh/')
LINE = re.compile(r'^(\d+)\s+([a-zA-Z_][a-zA-Z_0-9]*)\((.*)\)\s+=\s+(.+)$')
QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')
ROOT = '/research/d7/spc/yzyang4'
DATA = {ROOT+'/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl':'fixed_train',
        ROOT+'/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl':'fixed_dev',
        ROOT+'/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json':'fixed_cards'}
PREFIXES = {
    '/usr':'system_toolchain','/bin':'system_toolchain','/lib':'system_libraries','/lib64':'system_libraries','/etc':'system_config',
    '/sys':'sysfs_hardware_metadata','/proc':'proc_process_metadata','/dev':'device_or_shm',
    ROOT+'/venvs/critic-blackwell-g0-20260905-r5':'fixed_runtime',ROOT+'/venvs/exp':'fixed_runtime_backing',
    ROOT+'/worktrees/critic-g0-final-only-20260903-b':'fixed_training_source',
    ROOT+'/aira-dojo/.git':'source_git_metadata',
    ROOT+'/cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base':'fixed_base_model_cache',
    ROOT+'/critic-component-g0/runs/job-12499':'this_run_outputs',
    '/data/d0/y24/yzyang4/.local/share/uv':'runtime_backing',
    '/uac/y24/yzyang4/.local/share/uv/python':'runtime_backing',
    '/tmp/critic-g0-12499':'job_build_cache',
}

def classify(path):
    path = os.path.normpath(path)
    if BLOCK.search(path):
        return 'blocked'
    if path in DATA:
        return DATA[path]
    for prefix, label in PREFIXES.items():
        if path == prefix or path.startswith(prefix+'/'):
            return label
    if path == '/uac/y24/yzyang4/.gitconfig':
        return 'git_configuration'
    if re.fullmatch(r'/tmp/(?:cc[A-Za-z0-9_.-]+|tmp[A-Za-z0-9_.-]+)(?:/(?:test\.[co]|a\.out|stderr\.txt))?',path):
        return 'temporary_compiler_probe'
    return 'unknown_absolute'

before = TRACE.stat()
cwd, fds, pending = {}, {}, {}
counts, calls, issues, unresolved = Counter(),Counter(),Counter(),Counter()
digest = hashlib.sha256()
line_count = 0
for raw in TRACE.open('rb'):
    line_count += 1
    digest.update(raw)
    line = raw.decode('utf-8', errors='strict').rstrip('\n')
    assert not SECRET.search(line), 'credential_shape_no_disclosure'
    if '<unfinished ...>' in line:
        m = re.match(r'^(\d+)\s+(.*)<unfinished \.\.\.>$',line)
        assert m and m[1] not in pending
        pending[m[1]] = m[2]
        continue
    if 'resumed>' in line:
        m = re.match(r'^(\d+)\s+<\.\.\. \w+ resumed>(.*)$',line)
        assert m and m[1] in pending
        line = m[1]+' '+pending.pop(m[1])+m[2]
    m = LINE.match(line)
    if not m:
        issues['signal_or_exit' if '--- ' in line or '+++ ' in line else 'unparsed'] += 1
        continue
    pid, call, body, result = m.groups()
    calls[call] += 1
    if result.startswith('-1 '):
        continue
    if call not in ('open','openat','openat2','creat','execve','execveat','chdir','fchdir','getcwd'):
        continue
    quoted = QUOTED.findall(body)
    if not quoted:
        issues['no_path_'+call] += 1
        continue
    path = ast.literal_eval(quoted[0])
    assert not BLOCK.search(path), 'protected_path_observed_no_disclosure'
    resolved = path if path.startswith('/') else None
    base = None
    if call == 'getcwd':
        assert path.startswith('/')
        cwd[pid] = path
        continue
    if not resolved:
        if call in ('openat','openat2','execveat'):
            dirfd = body.split(',',1)[0].strip()
            if dirfd == 'AT_FDCWD':
                base = cwd.get(pid)
            elif re.fullmatch(r'\d+',dirfd):
                base = fds.get((pid,int(dirfd)))
        else:
            base = cwd.get(pid)
        if base:
            resolved = os.path.normpath(base+'/'+path)
    if call == 'chdir':
        if resolved:
            cwd[pid] = resolved
        else:
            cwd.pop(pid,None)
        continue
    if call.startswith('open') or call == 'creat':
        match = re.match(r'^(\d+)(?:\s|$)',result)
        assert match, 'unexpected_open_result'
        fd = (pid,int(match[1]))
        if resolved:
            fds[fd] = resolved
        else:
            fds.pop(fd,None)
    created_empty = call.startswith('open') and 'O_CREAT' in body and ('O_EXCL' in body or 'O_TRUNC' in body)
    if resolved:
        category = classify(resolved)
        if category == 'unknown_absolute' and created_empty and re.fullmatch(r'/tmp/[a-z0-9_]{8}',resolved):
            category = 'fresh_exclusive_tmp_probe' if 'O_EXCL' in body else 'unknown_absolute'
        if category == 'unknown_absolute':
            unresolved[(call,resolved,'absolute')] += 1
    else:
        if created_empty and path in ('cpu_adam.o','cpu_adam.o.d','cpu_adam_impl.o','cpu_adam_impl.o.d'):
            category = 'compiler_output_creation_cwd_unresolved'
        else:
            category = 'unresolved_relative'
            unresolved[(call,path,'relative')] += 1
    counts[category] += 1
after = TRACE.stat()
assert (before.st_size,before.st_mtime_ns) == (after.st_size,after.st_mtime_ns), 'trace_changed_during_read'
OUT.mkdir(mode=0o700)
with (OUT/'private_unresolved.json').open('x') as f:
    json.dump([[*key,n] for key,n in sorted(unresolved.items())],f)
result = {'trace_sha256':digest.hexdigest(),'trace_bytes':before.st_size,'trace_lines':line_count,
    'categories':dict(counts),'syscalls':dict(calls),'parse_issues':dict(issues),
    'pending_unfinished':len(pending),'credential_shape_hits':0,'protected_literal_hits':0,
    'unresolved_unique':len(unresolved),'observed_existing_file_opens_categorized':not unresolved,
    'all_output_cwd_resolved':counts['compiler_output_creation_cwd_unresolved'] == 0,
    'scope_certificate':False,
    'limitations':['%file does not trace fork/clone, close/dup, inherited file descriptors, network or file-content reads',
                   'directory-fd tracking is observational, not a complete descriptor-lifetime proof',
                   'no claim of adversarial OS sandboxing or formal dataset provenance qualification']}
with (OUT/'summary.json').open('x') as f:
    json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True,indent=2))
