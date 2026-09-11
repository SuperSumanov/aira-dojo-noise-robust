"""Remote CPU-only successor build: immutable prior roots, explicit derivation.

Copies ONLY the fixed source/config/release files, never old run outputs or keys.
Final source is checked against a real locally constructed Git tree inventory.
The 22-file old release is transformed only by documented path/hash/generator
bindings, the paid route front door, and child ledger/scope environment.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile

from forets_paid_budget_20260911 import MODEL, PROVIDER, AUTH, AUTH_SHA, initialize
from forets_paid_patch_20260911 import once

OLD=Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4')
OLD_CODE=Path('/research/d7/spc/yzyang4/forets-native-release-20260911-dAKj2b')
OLD_TREE='3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'
OLD_PREPARED='d6fcf987924bf696c8a6ea7fb252a6a634ad3fdac9de192a24eb07ec63fee76d'
OLD_RELEASE='e7c64f43032901716f4f3d5abf75a3e7d15f6417bd44e7e6e37b5fc5f8983706'
OLD_INVENTORY='e72e6f7ad5f500967e1ea243a05afc016a2ae7ad35c9262dedd80bd43d89b84f'
OLD_CODE_MANIFEST='563416f98a3d2bff8963976dea1485f23bc706dddf8e4e032222fd97ea520637'
PAID_MODULES=('forets_paid_budget_20260911.py','forets_paid_transport_20260911.py',
              'forets_paid_patch_20260911.py','forets_paid_route_20260911.py')


def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def read(path,digest=None):
    raw=path.read_bytes()
    if digest and sha(raw)!=digest:raise ValueError('prior artifact drift')
    return json.loads(raw)
def write(path,raw):
    with path.open('xb') as f:f.write(raw)
    return sha(raw)


def replace_paths(obj,root):
    if isinstance(obj,dict):return {k:replace_paths(v,root) for k,v in obj.items()}
    if isinstance(obj,list):return [replace_paths(v,root) for v in obj]
    if isinstance(obj,str):return obj.replace(str(OLD),str(root))
    return obj


def paid_config(value):
    """Require every configured LLM client to use exactly the new common route."""
    found=0
    def walk(obj):
        nonlocal found
        if isinstance(obj,dict):
            if 'client' in obj and 'generation_kwargs' in obj:
                if obj['client'].get('model_id')!='nvidia/nemotron-3-ultra-550b-a55b:free':
                    raise ValueError('unexpected existing LLM client')
                obj['client']['model_id']=MODEL
                kw=obj['generation_kwargs']
                kw['extra_body']={'provider':copy.deepcopy(PROVIDER)}
                kw['bounded_paid_budget_required']=True
                found+=1
            for v in obj.values():walk(v)
        elif isinstance(obj,list):
            for v in obj:walk(v)
    walk(value)
    if found!=4:raise ValueError('expected all four operator clients')
    return value


def build(stage):
    info=read(stage/'artifact.json')
    if info['base_tree']!=OLD_TREE:raise ValueError('wrong source base')
    if sha((stage/'source.tar').read_bytes())!=info['archive_sha256']:raise ValueError('archive drift')
    old=read(OLD/'prepared.json',OLD_PREPARED)
    code_manifest=read(OLD_CODE/'code-manifest.json',OLD_CODE_MANIFEST)
    code={}
    for name,digest in code_manifest['files'].items():
        raw=(OLD_CODE/name).read_bytes()
        if sha(raw)!=digest:raise ValueError('base controller drift')
        code[name]=raw
    root=Path(tempfile.mkdtemp(prefix='forets-paid-20260911-',dir='/research/d7/spc/yzyang4'))
    os.chmod(root,0o700)
    for d in ('source','configs','launchers','runs','code'):(root/d).mkdir(mode=0o700)
    with tarfile.open(stage/'source.tar') as archive:
        seen=set()
        for member in archive:
            if member.isdir():continue
            if not member.isfile() or member.name not in info['source_files'] or member.name in seen:
                raise ValueError('unexpected source member')
            target=root/'source'/member.name
            if not target.resolve().is_relative_to(root/'source'):raise ValueError('unsafe archive path')
            raw=archive.extractfile(member).read()
            if sha(raw)!=info['source_files'][member.name]:raise ValueError('source tree mismatch')
            target.parent.mkdir(parents=True,exist_ok=True);write(target,raw);seen.add(member.name)
        if seen!=set(info['source_files']):raise ValueError('incomplete source')
    inventory_sha=write(root/'source-files.json',encode(info['source_files']))
    rows,normalized=[],[]
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR=str(root),MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0,str(root/'source/src'));sys.path.append(str(OLD_CODE))
    from dojo.config_dataclasses.run import RunConfig
    from forets_e2e_package import common_config
    for row in old['run_configs']:
        original=read(OLD/'configs'/(row['run_id']+'.json'),row['config_sha256'])
        cfg=paid_config(replace_paths(original,root))
        typed=RunConfig.from_dict(cfg);typed.validate()
        if typed.to_typed_dict()!=cfg:raise ValueError('typed config roundtrip differs')
        digest=write(root/'configs'/(row['run_id']+'.json'),encode(cfg))
        rows.append(dict(row,config_sha256=digest))
        normalized.append(common_config(cfg,run_id=row['run_id'],run_dir=root/'runs'/row['run_id']))
    if any(normalized[i]!=normalized[i+1] for i in range(0,8,2)):
        raise ValueError('paired configs differ beyond selector')
    prepared=replace_paths(old,root)
    prepared.update(source_tree=info['source_tree'],base_source_tree=OLD_TREE,run_configs=rows,
        generator=MODEL,nominal_gpu_hours=2*280*2/60,source_archive_sha256=info['archive_sha256'],
        source_files=len(info['source_files']),plan_sha256=AUTH_SHA,preparation_commit=info['commit'],
        remaining=['fresh paid route per block'],checkpoint_training_template='UNKNOWN_FIXED_EXISTING_SERVICE',
        paired_config_sha256=[sha(json.dumps(normalized[i],sort_keys=True).encode()) for i in range(0,8,2)])
    prepared_sha=write(root/'prepared.json',encode(prepared))
    manifest=read(OLD/'manifest.json');manifest.update(source_tree=info['source_tree'],runs=rows)
    write(root/'manifest.json',encode(replace_paths(manifest,root)))
    for block in (1,2):write(root/'launchers'/f'block-{block}.json',encode(old['launcher']))
    correction_raw=(OLD/'allocation-budget-correction.json').read_bytes()
    correction_sha=write(root/'allocation-budget-correction.json',correction_raw)
    write(root/'PACKAGE_STATE.json',encode(dict(execution_allowed=False,readiness=False,
        package=str(root),supersedes=str(OLD),source_tree=info['source_tree'],paid_authorization_sha256=AUTH_SHA)))
    spec=json.loads(code['forets_native_e2e_release_20260911.json'])
    spec.update(package=str(root),source_tree=info['source_tree'],generator=MODEL,
        route_check_attempt_cap_per_block=2,paid_or_model_fallback=False,paid_generator=True,
        paid_authorization_sha256=AUTH_SHA,serial_transport_per_worker=True)
    release_raw=encode(spec);release_sha=sha(release_raw)
    replacements={str(OLD):str(root),OLD_TREE:info['source_tree'],OLD_PREPARED:prepared_sha,
                  OLD_RELEASE:release_sha,OLD_INVENTORY:inventory_sha}
    derivation={}
    for name,raw in code.items():
        if name=='forets_native_e2e_release_20260911.json':new=release_raw
        else:
            text=raw.decode()
            for oldstr,newstr in replacements.items():text=text.replace(oldstr,newstr)
            if name=='forets_native_context_20260911.py':
                text=once(text,'        additions = dict(DOJO_WORKER_IDENTITY_PATH=str(identity),',
                    "        additions = dict(FORETS_PAID_LEDGER=str(ROOT/'paid.sqlite'), FORETS_PAID_SCOPE=run_id,\n            DOJO_WORKER_IDENTITY_PATH=str(identity),")
            if name=='forets_native_run_20260911.py':
                start=text.index('def route(');end=text.index('\ndef main():',start)
                text=text[:start]+"def route(directory, block):\n    from forets_paid_route_20260911 import route as paid_route\n    return paid_route(directory, block)\n\n"+text[end:]
            if name in ('forets_stage_gate.py','check_forets_resilience_live_20260910.py'):
                text=text.replace('nvidia/nemotron-3-ultra-550b-a55b:free',MODEL)
                text=text.replace("('lite_llm.py', 'bounded_retry.py')","('lite_llm.py', 'bounded_retry.py', 'paid_budget.py', 'paid_transport.py')")
            if name=='forets_stage_gate.py':
                text=once(text,"    calls = receipt.get('calls', [])", "    from forets_paid_budget_20260911 import AUTH_SHA, snapshot\n    from forets_native_context_20260911 import ROOT\n    if (receipt.get('paid_authorization_sha256') != AUTH_SHA or receipt.get('paid_ledger') != str(ROOT/'paid.sqlite')\n            or snapshot(ROOT/'paid.sqlite')['stopped']):\n        raise RuntimeError('paid authorization or ledger invalid')\n    calls = receipt.get('calls', [])")
            new=text.encode()
        target=root/'code'/name;target.parent.mkdir(exist_ok=True,parents=True);write(target,new)
        derivation[name]=dict(base_sha256=sha(raw),derived_sha256=sha(new))
    for name in PAID_MODULES:write(root/'code'/name,(stage/name).read_bytes())
    os.chmod(root/'code/bin/singularity',0o700)
    files={str(p.relative_to(root/'code')):sha(p.read_bytes()) for p in (root/'code').rglob('*') if p.is_file()}
    write(root/'code/code-manifest.json',encode(dict(commit=info['commit'],
        base_controller_commit=code_manifest['commit'],files=files,derivation=derivation)))
    initialize(root/'paid.sqlite',[r['run_id'] for r in rows])
    write(root/'paid-authorization.json',encode(AUTH))
    report=dict(status='PAID_SUCCESSOR_PREPARED_NO_CALLS_NO_GPU',package=str(root),
        source_tree=info['source_tree'],commit=info['commit'],prepared_sha256=prepared_sha,
        source_inventory_sha256=inventory_sha,release_sha256=release_sha,configs=8,paired=4,
        authorization_sha256=AUTH_SHA,base_package_unchanged=True)
    write(root/'build.json',encode(report));print(json.dumps(report))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);a=p.parse_args();build(a.stage)
