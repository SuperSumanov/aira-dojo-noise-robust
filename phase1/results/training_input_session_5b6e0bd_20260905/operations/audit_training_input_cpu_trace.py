"""Observed successful file opens for own synthetic CPU run, not OS isolation."""
import ast,collections,hashlib,json,os,re,sys
from pathlib import Path
root=Path(sys.argv[1]);repeat=sys.argv[2]
assert root.parent==Path('/tmp') and root.name.startswith('train-input-session-') and root.resolve()==root
assert repeat in {'a','b'} and root.stat().st_uid==os.getuid()
trace=root/(repeat+'.trace');out=root/(repeat+'.trace_audit_v2.json')
block=re.compile(r'(?i)first[-_]?960|target[-_]?(?:300|522)|prospective_decision|label[_-]?vault|prediction[_-]?escrow|\.env(?:$|/)|/\.ssh/')
secret=re.compile(r'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})|Bearer\s+\S+')
line_re=re.compile(r'^(\d+)\s+([a-zA-Z_][a-zA-Z_0-9]*)\((.*)\)\s+=\s+(.+)$')
quoted=re.compile(r'"(?:[^"\\]|\\.)*"')
base='/research/d7/spc/yzyang4'
prefixes={str(root):'own_synthetic_code_and_outputs','/usr':'system','/bin':'system','/lib':'system','/lib64':'system','/etc':'system_config','/dev':'devices','/proc':'process_metadata','/sys':'system_metadata',base+'/venvs':'fixed_runtime_or_backing',base+'/aira-dojo/.git':'source_git_metadata','/data/d0/y24/yzyang4/.local/share/uv':'runtime_backing','/uac/y24/yzyang4/.local/share/uv':'runtime_backing'}
exact={base+'/worktrees/critic-g0-final-only-20260903-b/.git':'fixed_source_git_pointer','/uac/y24/yzyang4/.gitconfig':'git_config'}
def classify(p,body):
    p=os.path.normpath(p)
    if block.search(p):return 'PROTECTED'
    if p in exact:return exact[p]
    for prefix,c in prefixes.items():
        if p==prefix or p.startswith(prefix+'/'):return c
    if re.fullmatch(r'/tmp/tmp[a-zA-Z0-9_-]+(?:/.*)?',p):return 'python_temporary'
    return 'unknown'
before=trace.stat();digest=hashlib.sha256();pending={};cwd={};fds={};counts=collections.Counter();issues=collections.Counter();unknown=collections.Counter();n=0;created_temporary=set()
for raw in trace.open('rb'):
    n+=1;digest.update(raw);line=raw.decode().rstrip('\n')
    assert not secret.search(line),'credential_shape_no_disclosure'
    if '<unfinished ...>' in line:
        m=re.match(r'^(\d+)\s+(.*)<unfinished \.\.\.>$',line);assert m and m[1] not in pending
        pending[m[1]]=m[2];continue
    if 'resumed>' in line:
        m=re.match(r'^(\d+)\s+<\.\.\. \w+ resumed>(.*)$',line);assert m and m[1] in pending
        line=m[1]+' '+pending.pop(m[1])+m[2]
    m=line_re.match(line)
    if not m:
        issues['signal_or_exit' if '--- ' in line or '+++ ' in line else 'unparsed']+=1;continue
    pid,call,body,result=m.groups()
    if result.startswith('-1 '):continue
    if call not in {'open','openat','openat2','creat','execve','execveat','chdir','getcwd'}:continue
    strings=quoted.findall(body)
    if not strings:issues['pathless_'+call]+=1;continue
    p=ast.literal_eval(strings[0]);assert not block.search(p),'protected_path_no_disclosure'
    if call=='getcwd':cwd[pid]=p;continue
    resolved=p if p.startswith('/') else None
    if not resolved:
        directory=body.split(',',1)[0].strip() if call in {'openat','openat2','execveat'} else 'AT_FDCWD'
        start=cwd.get(pid) if directory=='AT_FDCWD' else fds.get((pid,directory))
        if start:resolved=os.path.normpath(start+'/'+p)
    if call=='chdir':
        if resolved:cwd[pid]=resolved
        else:cwd.pop(pid,None)
        continue
    if call.startswith('open') or call=='creat':
        fd=re.match(r'^\d+',result);assert fd
        if resolved:fds[(pid,fd[0])]=resolved
        else:fds.pop((pid,fd[0]),None)
    c=classify(resolved,body) if resolved else 'unresolved_relative'
    if c=='unknown' and re.fullmatch(r'/tmp/(?:cc[A-Za-z0-9.]+|[a-z0-9_]{8}|pytorch-errorfile-[a-z0-9_]+\.pickle)',resolved):
        if call in {'open','openat','openat2','creat'} and 'O_CREAT' in body and ('O_EXCL' in body or 'O_TRUNC' in body):
            created_temporary.add(resolved)
        if resolved in created_temporary:c='observed_created_or_truncated_temporary'
    assert c!='PROTECTED','protected_path_no_disclosure'
    counts[c]+=1
    if c in {'unknown','unresolved_relative'}:unknown[(call,resolved or p)]+=1
after=trace.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
result={'trace_sha256':digest.hexdigest(),'trace_bytes':before.st_size,'lines':n,'categories':dict(counts),'parse_issues':dict(issues),'pending':len(pending),'unknown_unique':len(unknown),'unknown':[[*k,v] for k,v in sorted(unknown.items())],'credential_shape_hits':0,'protected_literal_hits':0,'observed_opens_categorized':not unknown and not pending and not issues['unparsed'],'scope_certificate':False,'limitations':['file syscalls only, no inherited descriptors/network/content coverage','fd/cwd tracking is observational and not complete lifetime tracking','Python temp directory accesses not a proof of absence of other files','not actual provenance qualification or unblinding permission']}
with out.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
