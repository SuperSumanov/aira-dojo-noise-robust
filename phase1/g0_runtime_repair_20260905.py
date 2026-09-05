"""Recover the missing native Ninja executable in a new, version-identical G0 venv.

No corpus or model inputs are opened. CPU checking compiles the actual CPU Adam
extension and compares small tensor updates; it does not certify GPU execution.
"""
import argparse
import contextlib
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

BASE = Path('/research/d7/spc/yzyang4')
OLD = BASE/'venvs/critic-blackwell-g0-20260903-selective'
TARGET = BASE/'venvs/critic-blackwell-g0-20260905-r5'
SETUP = BASE/'critic-component-g0/runtime-repair-20260905-r5'
CLOSURE = BASE/'critic-component-g0/runtime-setup-20260903-r3/dependency_closure.json'
CLOSURE_SHA = '5fad91f03344543e5389d0bf85438256b3eb4fed5aa0e8928f7c36e9875bf017'
NINJA = BASE/'venvs/critic-blackwell-g0-20260903-overlay/bin/ninja'
NINJA_SHA = '696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as fh:
        for block in iter(lambda: fh.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def record(name, obj):
    with (SETUP/name).open('x', encoding='utf-8') as fh:
        json.dump(obj, fh, sort_keys=True, indent=2)
        fh.write('\n')


def check_layout():
    assert digest(CLOSURE) == CLOSURE_SHA
    plan = json.loads(CLOSURE.read_text())
    for rel, backing in plan['links'].items():
        for prefix in (OLD, TARGET):
            link = prefix/'lib/python3.11/site-packages'/rel
            assert link.is_symlink() and str(link.resolve(strict=True)) == backing
    assert digest(TARGET/'bin/ninja') == digest(NINJA) == NINJA_SHA
    assert not (OLD/'bin/ninja').exists(), 'old runtime must remain unchanged'
    return plan


def create():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    assert not TARGET.exists() and not SETUP.exists()
    assert digest(CLOSURE) == CLOSURE_SHA and digest(NINJA) == NINJA_SHA
    plan = json.loads(CLOSURE.read_text())
    assert 'ninja' not in plan['console_scripts']
    SETUP.mkdir(mode=0o700)
    record('creation_intent.json', {'old':str(OLD),'new':str(TARGET),'closure_sha256':CLOSURE_SHA,
           'native_executable_sha256':NINJA_SHA,'model_changes':False,'dependency_version_changes':False})
    subprocess.run([BASE/'venvs/exp/bin/python','-m','venv','--without-pip',TARGET],check=True)
    site = TARGET/'lib/python3.11/site-packages'
    for rel, backing in sorted(plan['links'].items()):
        assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
        source = Path(backing)
        assert str(source).startswith(str(BASE/'venvs')+'/')
        old = OLD/'lib/python3.11/site-packages'/rel
        assert old.is_symlink() and str(old.resolve(strict=True)) == backing
        dest = site/rel
        assert not dest.exists() and not dest.is_symlink()
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.symlink_to(backing, target_is_directory=source.is_dir())
    for name, value in sorted(plan['console_scripts'].items()):
        assert '/' not in name and '\\' not in name
        module, attr = value.split(':',1)
        attr = attr.split(' ',1)[0]
        dest = TARGET/'bin'/name
        assert not dest.exists()
        with dest.open('x') as fh:
            fh.write(f'#!{TARGET}/bin/python\nimport sys\nfrom {module} import {attr}\nif __name__ == "__main__":\n    sys.exit({attr}())\n')
        dest.chmod(0o755)
    # This is a wheel-installed native executable, not a Python console entry.
    with (TARGET/'bin/ninja').open('xb') as fh:
        fh.write(NINJA.read_bytes())
    (TARGET/'bin/ninja').chmod(0o755)
    check_layout()
    record('CREATED.json', {'status':'RUNTIME_CREATED_NOT_GPU_CERTIFIED','package_count':len(plan['packages']),
           'link_count':len(plan['links']),'console_script_count':len(plan['console_scripts']),
           'native_executables_added':['ninja'],'ninja_sha256':NINJA_SHA,'old_runtime_modified':False,
           'script_sha256':digest(__file__)})
    print(json.dumps({'status':'RUNTIME_CREATED_NOT_GPU_CERTIFIED','target':str(TARGET)}))


def cpu_check(label):
    assert label in ('login','target-node')
    assert Path(sys.prefix) == TARGET
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    assert os.environ.get('MAX_JOBS') == '2'
    plan = check_layout()
    observed = {d.metadata['Name'].lower().replace('_','-'):d.version for d in md.distributions()}
    assert observed == {k:v['version'] for k,v in plan['packages'].items()}
    assert shutil.which('ninja') == str(TARGET/'bin/ninja')
    ninja_version = subprocess.check_output(['ninja','--version'],text=True).strip()
    compiler = subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
    started = time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from torch.utils.cpp_extension import verify_ninja_availability, CUDA_HOME
        from deepspeed.ops.adam import DeepSpeedCPUAdam
        assert not torch.cuda.is_initialized()
        verify_ninja_availability()
        torch.manual_seed(6)
        torch.set_num_threads(2)
        p = torch.nn.Parameter(torch.randn(32,dtype=torch.float32))
        q = torch.nn.Parameter(p.detach().clone())
        adam = DeepSpeedCPUAdam([p],lr=1e-5,betas=(0.9,0.999),eps=1e-8,
                               weight_decay=0.01,adamw_mode=True)
        reference = torch.optim.AdamW([q],lr=1e-5,betas=(0.9,0.999),eps=1e-8,
                                      weight_decay=0.01,foreach=False)
        errors = []
        for _ in range(3):
            gradient = torch.randn_like(p)
            p.grad = gradient.clone()
            q.grad = gradient.clone()
            adam.step()
            reference.step()
            errors.append(float((p-q).abs().max()))
        assert max(errors) <= 1e-6, errors
        assert not torch.cuda.is_initialized()
        builder_path = Path(sys.modules['deepspeed.ops.op_builder.builder'].__file__)
    result = {'status':'REAL_CPU_ADAM_COMPILE_INIT_UPDATE_PASS','seed':6,'tensor_elements':32,
              'updates':3,'max_absolute_error_by_update':errors,'tolerance':1e-6,
              'gpu_context_created':False,'gpu_execution_validated':False,'model_fits':0,
              'ninja_version':ninja_version,'ninja_sha256':digest(TARGET/'bin/ninja'),
              'compiler':compiler,'cuda_home_detected':CUDA_HOME,'package_count':len(observed),
              'elapsed_seconds':time.monotonic()-started,'hostname':os.uname().nodename,
              'deepspeed_builder_sha256':digest(builder_path),'script_sha256':digest(__file__),
              'compiled_cache_not_reused_for_gpu_job':True}
    record('cpu_check_'+label+'.json',result)
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['create','cpu-check','layout'])
    parser.add_argument('--label',default='login',choices=['login','target-node'])
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'create':
        create()
    elif args.action == 'layout':
        check_layout()
        print(json.dumps({'status':'LAYOUT_AND_NINJA_HASH_PASS'}))
    else:
        cpu_check(args.label)
