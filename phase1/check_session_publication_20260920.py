"""Read-only exact staged/ahead blob scan; counts only, never matching text."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='aa76c3cad52b991a4513d828bd06993def9c9c47'
PATTERN=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|AKIA[A-Z0-9]{16})')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def main():
    staged=git('diff','--cached','--name-only','-z').decode().split('\0');staged=[p for p in staged if p]
    changed=git('diff','--name-only','-z',BASE,'HEAD').decode().split('\0');changed=[p for p in changed if p]
    entries=[(':',p) for p in staged]+[('HEAD:',p) for p in changed];hits=0;names=0;private_keys=0;fidelity=0
    for prefix,path in entries:
        raw=git('show',prefix+path);hits+=len(PATTERN.findall(raw));names+=bool(re.search(r'(?i)(env|key|token|secret)',path))
        if '/results/' in path and path.endswith(('.json','.csv')):
            if prefix==':' and raw!=(ROOT/path).read_bytes():fidelity+=1
            if path.endswith('.json'):
                def walk(v):
                    nonlocal private_keys
                    if isinstance(v,dict):
                        for k,x in v.items():
                            private_keys+=k.lower() in {'code','response','prompt','term_out','api_key','primary_key','answer','authorization'};walk(x)
                    elif isinstance(v,list):
                        for x in v:walk(x)
                walk(json.loads(raw))
    out=dict(base=BASE,head=git('rev-parse','HEAD').decode().strip(),staged_files=len(staged),ahead_files=len(changed),credential_hits=hits,sensitive_filename_hits=names,private_payload_keys=private_keys,byte_fidelity_failures=fidelity,paths=sorted(set(staged+changed)))
    print(json.dumps(out))
    if hits or names or private_keys or fidelity:raise SystemExit(1)
if __name__=='__main__':main()
