"""Credential-first remote-only read of an exact documentation delta."""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone

REPO = '/research/d7/spc/yzyang4/aira-dojo'
OLD = '54e8a0e3458e12443658104d244e2b6d9e553451'
NEW = '67e371960802d804bdab8b9b55f3dde2ed98f125'
PATHS = ['src/mle_critic/docs/data/OVERVIEW_MINE.md',
         'src/mle_critic/docs/evaluation/BRADLEY_TERRY_EVALUATION.md',
         'src/mle_critic/docs/evaluation/E2E_EVALUATION.md']
SECRET = re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|AKIA[A-Z0-9]{16})')
ASSIGN = re.compile(r'(?i)((?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*)[\'\"]?[^\s\'\"`]+')
PROTECTED = re.compile(r'(?i)(first[-_ ]?960|target[-_ ]?(300|522)|prediction[_-]?escrow|outcome[_-]?vault)')

def main():
    cmd = 'source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1; git -C '+REPO+' fetch --quiet --no-tags fork dojo-reproduce'
    result = subprocess.run(['bash','-c',cmd],capture_output=True,timeout=80)
    if result.returncode:
        print(json.dumps({'status':'FETCH_FAILED','returncode':result.returncode})); return
    records=[]
    for path in PATHS:
        raw=subprocess.check_output(['git','-C',REPO,'diff','--no-ext-diff','--unified=2',OLD,NEW,'--',path],stderr=subprocess.PIPE,timeout=20)
        content=raw.decode('utf-8')
        hits=len(SECRET.findall(content))
        content=SECRET.sub('[REDACTED]',content)
        content=ASSIGN.sub(r'\1[REDACTED]',content)
        protected=bool(PROTECTED.search(content))
        records.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),credential_shape_hits=hits,
                            protected_scope_match=protected,redacted_diff=None if protected else content))
    print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),old=OLD,new=NEW,records=records),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
