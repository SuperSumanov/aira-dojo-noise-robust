import hashlib
import json
from pathlib import Path
import pytest
from phase1.critic_fa2_preflight import verify_overlay, numerical_check, math_reference


def fixture(tmp_path):
    root=tmp_path/'overlay';root.mkdir();(root/'member.py').write_bytes(b'fixed')
    obj={'classification':'ISOLATED_FA2_CPU_BUILD_NOT_GPU_ACCEPTANCE',
         'overlay_files':{'member.py':hashlib.sha256(b'fixed').hexdigest()}}
    path=tmp_path/'BUILT.json';path.write_text(json.dumps(obj))
    return root,path,hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_overlay(tmp_path):
    root,path,h=fixture(tmp_path)
    assert verify_overlay(root,path,h)['overlay_files']


@pytest.mark.parametrize('kind',['digest','member','extra','missing'])
def test_drift_rejected(tmp_path,kind):
    root,path,h=fixture(tmp_path)
    if kind=='digest':h='0'*64
    if kind=='member':(root/'member.py').write_bytes(b'changed')
    if kind=='extra':(root/'extra.py').write_bytes(b'new')
    if kind=='missing':(root/'member.py').unlink()
    with pytest.raises((ValueError,FileNotFoundError)):verify_overlay(root,path,h)


def test_inventory_traversal(tmp_path):
    root,path,h=fixture(tmp_path)
    obj=json.loads(path.read_text());obj['overlay_files']={'../outside':h};path.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='unsafe_build_member'):
        verify_overlay(root,path,hashlib.sha256(path.read_bytes()).hexdigest())


def test_math_mask_and_grouping():
    torch=pytest.importorskip('torch')
    q=torch.zeros(1,2,2,1,requires_grad=True);k=torch.zeros(1,2,1,1,requires_grad=True)
    v=torch.tensor([[[[1.]],[[3.]]]],requires_grad=True)
    out=math_reference(q,k,v)
    assert torch.equal(out,torch.tensor([[[[1.],[1.]],[[2.],[2.]]]]))
    out.sum().backward();assert torch.equal(v.grad,torch.tensor([[[[3.]],[[1.]]]]))


def test_numerical_positive_and_negative_controls():
    torch=pytest.importorskip('torch')
    x=torch.ones(2,3)
    assert numerical_check(x,x)['relative_l2']==0
    for y in (x*1.1,x*float('nan'),x*float('inf'),x[:1]):
        with pytest.raises(ValueError):numerical_check(y,x)
