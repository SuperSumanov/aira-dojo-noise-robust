import ast
import inspect
from pathlib import Path
import pytest
from phase1.scripts import build_fa2_cpu_20260907 as old
from phase1.scripts import build_fa2_ampere_cpu_20260907 as new

def test_core_security_and_stage_functions_unchanged():
    for name in ('sha','record','verify_source_contents','invoke'):
        assert inspect.getsource(getattr(old,name))==inspect.getsource(getattr(new,name))
    assert new.ROOT!=old.ROOT and new.ROOT.name=='flash-attn-build-ampere-20260907-r1'
    for name in ('RUNTIME','HOST_CXX','HOST_SHA','SDIST_SHA','WHEEL_SHA'):
        assert getattr(old,name)==getattr(new,name)

def test_compiler_only_architecture_diff():
    assert inspect.getsource(new.compiler_check)==inspect.getsource(old.compiler_check).replace('sm_120','sm_80')

def test_explicit_ampere_configuration_and_bounds():
    s=inspect.getsource(new.main)
    assert "'SLURM_CPUS_PER_TASK') == '8'" in s
    assert "FLASH_ATTN_CUDA_ARCHS='80'" in s and "MAX_JOBS='4'" in s and "NVCC_THREADS='2'" in s
    assert 'source],env,4800,source)' in s and "'gpu_reservation_upper_bound_seconds': 5760" in s
    assert "meminfo['MemAvailable'] >= 32*1024*1024" in s
    assert "'arch': '80'" in s and 'sm_120' not in s and "ARCHS='120'" not in s
    assert 'verify_source_contents' in s and "torch.cuda.is_initialized()" in s

def test_batch_script_is_one_reserved_gpu_not_model_job():
    p=Path(new.__file__).with_suffix('.sbatch');s=p.read_text()
    for item in ('--cpus-per-task=8','--gres=gpu:1','--nodelist=gpu37','--time=01:30:00',
                 '--mem=0','--no-requeue',"CUDA_VISIBLE_DEVICES=''",'FA2_BUILD_SCRIPT'):
        assert item in s
    assert '--gres=gpu:2' not in s

def test_separate_combined_engineering_envelope():
    core_upper=9423+5760+3840
    alternative=5760+2*(3600+300+60)
    assert core_upper==19023 and alternative==13680
    assert core_upper+alternative==32703<=36000

@pytest.mark.parametrize('tag',['job-bad','../x','job-1/x','', 'gpu'])
def test_bad_compiler_tag_rejected_before_access(tag):
    with pytest.raises(AssertionError):new.compiler_check(tag)
