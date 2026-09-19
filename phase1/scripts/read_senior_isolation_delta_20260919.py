"""Read only the new interpreter design delta, with remote-first redaction."""
import hashlib, json, subprocess
from read_senior_delta_20260919 import REPO, SECRET, ASSIGN, PROTECTED

OLD = '67e371960802d804bdab8b9b55f3dde2ed98f125'
NEW = 'e4181fac5edb319e14d4d819088778d5d2708912'
PATH = 'src/mle_critic/docs/runtime/interpreters/CHROOT_PYTHON_INTERPRETER_ISOLATION_PLAN.md'

def main():
    cmd = 'source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1; git -C '+REPO+' fetch --quiet --no-tags fork dojo-reproduce'
    result = subprocess.run(['bash','-c',cmd],capture_output=True,timeout=80)
    if result.returncode:
        raise RuntimeError('remote fetch failed; raw diagnostics withheld')
    raw = subprocess.check_output(['git','-C',REPO,'diff','--no-ext-diff','--unified=2',OLD,NEW,'--',PATH],stderr=subprocess.PIPE,timeout=20)
    content = raw.decode('utf-8')
    protected = bool(PROTECTED.search(content))
    safe = ASSIGN.sub(r'\1[REDACTED]', SECRET.sub('[REDACTED]',content))
    print(json.dumps(dict(old=OLD,new=NEW,path=PATH,sha256=hashlib.sha256(raw).hexdigest(),
        credential_shape_hits=len(SECRET.findall(content)),protected_scope_match=protected,
        redacted_diff=None if protected else safe),ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
