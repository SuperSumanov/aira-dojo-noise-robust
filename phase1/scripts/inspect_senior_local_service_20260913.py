"""Fetch metadata, then emit only credential-redacted service documentation."""
import hashlib
import json
import re
import subprocess

COMMIT='be9335348b569086ef9b0af36a15b13e61fec45c'
PATH='src/mle_critic/docs/evaluation/LOCAL_VLLM_SERVER.md'
REPO='/research/d7/spc/yzyang4/aira-dojo'

def run():
    command='set +eu; source "$HOME/env_setup.sh" >/dev/null 2>&1; exec git -C '+REPO+' fetch https://github.com/SuperSumanov/aira-dojo-noise-robust.git dojo-reproduce'
    p=subprocess.run(['bash','-c',command],capture_output=True,timeout=60)
    if p.returncode:raise RuntimeError('remote fetch failed; raw output suppressed')
    raw=subprocess.run(['git','-C',REPO,'show',COMMIT+':'+PATH],capture_output=True,check=True).stdout
    text=raw.decode();patterns=[r'(?<![A-Za-z0-9])sk-[A-Za-z0-9_.-]+',r'AKIA[0-9A-Z]{16}',r'gh[pousr]_[A-Za-z0-9]{20,}',
        r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----']
    hits=0
    for pattern in patterns:
        text,n=re.subn(pattern,'[REDACTED_CREDENTIAL]',text);hits+=n
    if any(re.search(pattern,text) for pattern in patterns):raise ValueError('credential redaction failed')
    print(json.dumps(dict(commit=COMMIT,path=PATH,raw_sha256=hashlib.sha256(raw).hexdigest(),redacted_shapes=hits)))
    print(text)

if __name__=='__main__':run()
