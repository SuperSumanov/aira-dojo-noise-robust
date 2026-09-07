import copy
import numpy as np
import pytest
from phase1.shared_record_noise import matrix,closed_form,incidence
from phase1.verify_shared_record_noise import verify

def test_closed_form_and_gls_agree():
    result=verify(matrix());assert result['max_absolute_error']<=1e-9
    assert result['fully_shared_record_cycle_gain_zero'] and not result['model_effect_measured']

@pytest.mark.parametrize('kind',['value','scope','grid','duplicate','count','nonfinite','mean','claim'])
def test_verifier_refuses_wrong_evidence(kind):
    v=matrix()
    if kind=='value':v['rows'][0]['full_variances'][0]+=0.1
    elif kind=='scope':v['classification']='REAL_MODEL_GAIN'
    elif kind=='grid':v['rows'][0]['rho']=.1
    elif kind=='duplicate':v['rows'][1]=copy.deepcopy(v['rows'][0])
    elif kind=='count':v['rows'][0]['nodes']=7
    elif kind=='nonfinite':v['rows'][0]['tree_variances'][0]=float('nan')
    elif kind=='mean':v['rows'][0]['tree_mean']=2.
    else:v['true_execution_noise_estimated']=True
    with pytest.raises(ValueError):verify(v)

@pytest.mark.parametrize('rho',[-.1,1.1,float('nan'),True])
def test_bad_rho_rejected(rho):
    with pytest.raises(ValueError):closed_form(3,[(0,1),(1,2)],[(0,1)],rho)

def test_disconnected_and_repeated_edges_rejected():
    with pytest.raises(ValueError):closed_form(4,[(0,1),(2,3)],[(0,1)],.5)
    with pytest.raises(ValueError):incidence(3,[(0,1),(1,0)])

def test_orientation_row_and_vertex_permutation_invariance():
    edges=[(0,1),(1,2),(2,3),(3,4),(4,5),(0,4),(2,5)];targets=[(0,1),(3,4)]
    permutation=[3,1,4,0,5,2]
    for rho in (0,.25,.5,.75,1):
        a=closed_form(6,edges,targets,rho)
        b=closed_form(6,[(y,x) for x,y in edges[::-1]],targets,rho)
        c=closed_form(6,[(permutation[x],permutation[y]) for x,y in edges],[(permutation[x],permutation[y]) for x,y in targets],rho)
        np.testing.assert_allclose(a,b,rtol=0,atol=1e-9);np.testing.assert_allclose(a,c,rtol=0,atol=1e-9)

@pytest.mark.parametrize('n',[4,7,9])
def test_non_tree_incomplete_graph_also_agrees(n):
    from phase1.verify_shared_record_noise import direct_gls
    pairs=[(i,i+1) for i in range(n-1)]+[(0,n-1),(0,2)]
    targets=[(0,1),(1,n-1)]
    for rho in (0,.25,.5,.75,1):
        np.testing.assert_allclose(closed_form(n,pairs,targets,rho),direct_gls(n,pairs,targets,rho),atol=1e-9,rtol=0)
