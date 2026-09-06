import copy
import pytest
from phase1.global_local_cpu_adam_resume import replay_spec
from phase1.global_local_execution_plan import PlanError


def group():return {'params':[],'lr':1e-5,'betas':(.9,.999),'eps':1e-8,'weight_decay':.01,'bias_correction':True}


def test_identical_closed_groups_are_supported_readonly():
    groups=[group(),group()];before=copy.deepcopy(groups)
    assert replay_spec(groups,2)=={k:v for k,v in group().items() if k!='params'}
    assert groups==before


@pytest.mark.parametrize('steps',[0,-1,True,1.5,100001])
def test_invalid_step(steps):
    with pytest.raises(PlanError):replay_spec([group()],steps)


@pytest.mark.parametrize('field,value',[('params',[0]),('lr',float('nan')),('lr',0.),('eps',0.),
    ('weight_decay',-.1),('bias_correction',False),('betas',[.9,.999]),('betas',(.9,1.)),('betas',(True,.9))])
def test_bad_group(field,value):
    g=group();g[field]=value
    with pytest.raises(PlanError):replay_spec([g],2)


def test_mixed_groups_forbidden():
    g=group();g['betas']=(.8,.999)
    with pytest.raises(PlanError,match='mixed_groups'):replay_spec([group(),g],2)
