"""Read only pinned placement helpers before a pre-execution node migration."""
import ast
import hashlib
import json
from pathlib import Path
import re

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'scheduling-live-search-20261009-v2'
SECRET=re.compile(rb'(?i)(?<![a-z0-9_-])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def main():
    p=json.loads((ROOT/'plan.json').read_bytes())
    targets=[(BASE/'repair-replace-dev-20260927-v1/tests/fresh_first_slot_gpu27_20260927.py',
              'daf6b0e80db3577aa5f3219a47e166171958672cae00249248251bf78fd51857',
              ('native_uuids','clean_env','local_key'))]
    rel='forets_native_cuda_identity_20260911.py'
    targets.append((ROOT/rel,p['files'][rel],('identity',)))
    rel='source/src/dojo/core/interpreters/jupyter/jupyter_interpreter.py'
    targets.append((ROOT/rel,p['files'][rel],('_slurm_gateway_port','_gateway_port')))
    for path,pin,names in targets:
        raw=path.read_bytes()
        if SECRET.search(raw) or hashlib.sha256(raw).hexdigest()!=pin:
            raise ValueError('source security/hash failed')
        code=raw.decode()
        for n in ast.walk(ast.parse(code)):
            if isinstance(n,ast.FunctionDef) and n.name in names:
                print(path.name, ast.get_source_segment(code,n),sep='\n')

if __name__=='__main__':main()
