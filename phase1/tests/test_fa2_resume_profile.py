import os
from pathlib import Path
import pytest
from phase1.scripts import resume_fa2_build_20260907 as m


def fixture(tmp_path,monkeypatch):
    if not hasattr(os,'getuid'):monkeypatch.setattr(os,'getuid',lambda:0,raising=False)
    root=tmp_path/'build';root.mkdir();p=root/'a.o';p.write_bytes(b'\x7fELFsynthetic-not-real-compile')
    line=f'0\t5\t6\t{p}\tabc123\n'
    return root,p,'# ninja log v7\n'+line


def test_completed_hashes(tmp_path,monkeypatch):
    root,p,log=fixture(tmp_path,monkeypatch);v=m.completed_objects(log,root)
    assert v=={'a.o':{'bytes':p.stat().st_size,'sha256':m.sha(p),'command_hash':'abc123'}}


@pytest.mark.parametrize('bad',['version','duplicate','missing','nonelf','outside','extension','times','command','malformed'])
def test_completed_rejects(tmp_path,monkeypatch,bad):
    root,p,log=fixture(tmp_path,monkeypatch)
    if bad=='version':log=log.replace('v7','v5')
    elif bad=='duplicate':log+=log.splitlines(True)[1]
    elif bad=='missing':p.unlink()
    elif bad=='nonelf':p.write_bytes(b'not-an-ELF-object')
    elif bad=='outside':log=log.replace(str(p),str(tmp_path/'a.o'))
    elif bad=='extension':log=log.replace('.o\t','.so\t')
    elif bad=='times':log=log.replace('0\t5\t','9\t5\t')
    elif bad=='command':log=log.replace('abc123','not-hex')
    elif bad=='malformed':log+='broken\n'
    with pytest.raises(ValueError):m.completed_objects(log,root)


def test_sbatch_scope_and_compiler_contract():
    p=Path(m.__file__).with_suffix('.sbatch').read_text()
    assert '#SBATCH --time=01:30:00' in p and '#SBATCH --gres=gpu:1' in p
    assert '#SBATCH --nodelist=gpu37' in p and '#SBATCH --cpus-per-task=4' in p
    assert '\nexport CUDA_VISIBLE_DEVICES= ' in p and '+export' not in p
    assert m.COMPILER_SECONDS==4800 and m.GPU_CAP==5760
    assert 7297+2126==9423 and 9423+5760+3840==19023<=21600


@pytest.mark.parametrize('key,value',[('prior_job','12635'),('prior_state','COMPLETED'),
    ('prior_elapsed_seconds',2100),('prior_gpu_seconds_total',7297),('new_compile_seconds',4900),
    ('new_gpu_seconds_upper_bound',5800),('combined_gpu_seconds_upper_bound',18000)])
def test_wrong_prior_or_budget_rejected_before_io(key,value):
    v={'prior_job':'12641','prior_state':'FAILED','prior_elapsed_seconds':2126,'prior_gpu_seconds_total':9423,
       'new_compile_seconds':4800,'new_gpu_seconds_upper_bound':5760,'combined_gpu_seconds_upper_bound':19023}
    v[key]=value
    with pytest.raises(ValueError):m.verify_prior(v)


def test_duplicate_receipt_field(tmp_path,monkeypatch):
    if not hasattr(os,'getuid'):monkeypatch.setattr(os,'getuid',lambda:0,raising=False)
    p=tmp_path/'r.json';p.write_text('{"same":1,"same":2}')
    with pytest.raises(ValueError,match='duplicate'):m.read(p)
