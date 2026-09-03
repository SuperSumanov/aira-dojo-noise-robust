"""Guard fault tests on synthetic events / copies of our own toy checkpoints."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


root=Path('/tmp/global-local-ddp-20260904-sfYGISUT')
out=root/'fault-tests-r1';out.mkdir(mode=0o700)
verifier=load('independent_ddp_verifier',root/'verify.py')
original=root/'run-r1/w2-G_to_L-prefix'
tests=[]
for mode in ('missing_rank_file','missing_rank_manifest_entry','corrupt_rank_bytes'):
    case=out/mode;case.mkdir(mode=0o700)
    manifest=json.loads((original/'manifest.json').read_text())
    for rank in (0,1):
        if mode=='missing_rank_file' and rank==1: continue
        shutil.copyfile(original/f'rank-{rank}.pt',case/f'rank-{rank}.pt')
    if mode=='missing_rank_manifest_entry': del manifest['rank_files']['rank-1.pt']
    if mode=='corrupt_rank_bytes':
        p=case/'rank-1.pt';b=p.read_bytes();p.write_bytes(b[:-1]+bytes([b[-1]^1]))
    (case/'manifest.json').write_text(json.dumps(manifest))
    try: verifier.read(case)
    except (AssertionError,FileNotFoundError): tests.append({'test':mode,'rejected':True})
    else: raise AssertionError('corrupt_checkpoint_accepted')

guard=load('input_guard',root/'phase1/historical_train_encoding_readiness.py')
opens,denied=guard.install_access_guard(out)
# Emit audit events only: no attempt to actually read any protected file.
for name,path,allow in (
    ('train_read',guard.TRAIN,True),
    ('library_vaultgemma_python_source',guard.TRANSFORMERS_PACKAGE/'models/vaultgemma/modeling_vaultgemma.py',True),
    ('future_vault_read',guard.BASE/'prospective_decision_v1/vault/canary.jsonl',False),
    ('dev_read',guard.TRAIN.with_name('dev.jsonl'),False),
    ('test_read',guard.TRAIN.with_name('test.jsonl'),False),
    ('model_weights',guard.MODEL/'model.safetensors',False),
):
    try: sys.audit('open',str(path),'r',os.O_RDONLY)
    except PermissionError: assert not allow
    else: assert allow
    tests.append({'test':name,'expected_policy_observed':True,'synthetic_audit_event_only':True})
try: sys.audit('open',str(guard.TRAIN),'w',os.O_WRONLY)
except PermissionError: tests.append({'test':'train_write','rejected':True,'synthetic_audit_event_only':True})
else: raise AssertionError('write_allowed')
try: sys.audit('socket.connect',None,('127.0.0.1',1))
except PermissionError: tests.append({'test':'network','rejected':True,'synthetic_audit_event_only':True})
else: raise AssertionError('network_allowed')
result={'status':'PASS_FAULT_CASES','tests':tests,'research_data_content_reads':0,'model_fits':0,
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'summary.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
