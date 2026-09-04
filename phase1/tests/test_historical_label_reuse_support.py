import pytest

from phase1.historical_label_reuse_support import analyze, pairs, project, graph, exposure
from phase1.verify_historical_label_reuse_support import recompute, inventory


def fixture():
    local=[('a','b'),('b','c'),('d','e')]
    global_all=[('a','c'),('c','d'),('a','x'),('x','y'),('a','z'),('a','b'),('a','missing')]
    grouped={'r1':[{'id':x,'task':{'name':'t1'}} for x in 'abcdexy'],
             'r2':[{'id':'z','task':{'name':'t1'}}]}
    return local,global_all,grouped


def as_rows(edges):
    return [dict(better=a,worse=b,intask_split='train') for a,b in edges]


def test_exact_partition_graph_and_independent_recomputation():
    l,g,c=fixture(); r,t=project(c)
    a=analyze(l,g,r,t)
    assert a==recompute(as_rows(l),as_rows(g),c)
    assert a['global_endpoint_partition']=={'both_endpoints_already_local':2,'one_endpoint_additional':1,'both_endpoints_additional':1}
    assert a['additional_global_endpoints']==2
    assert a['reusable_endpoint_coverage']==3
    assert a['reused_within_local_component_pairs']==a['reused_between_local_component_pairs']==1
    assert a['additional_incidence_rank']==1
    assert a['local_plus_reusable_graph']==dict(edges=5,endpoints=5,components=1,incidence_rank=4,cycle_edges=1)
    assert not a['new_pool_materialized'] and not a['effect_eligible']


def test_input_order_and_orientation_invariance():
    l,g,c=fixture(); r,t=project(c)
    reverse=lambda e:pairs(as_rows([(b,a) for a,b in reversed(e)]))
    assert analyze(l,g,r,t)==analyze(reverse(l),reverse(g),r,t)


def test_no_reuse_is_reported_without_invention():
    l,_,c=fixture(); r,t=project(c)
    a=analyze(l,[('x','y')],r,t)
    assert a['reusable_global_pairs']==a['additional_incidence_rank']==0
    assert a['reusable_exposure']['top_decile_endpoint_visit_share'] is None
    assert a==recompute(as_rows(l),as_rows([('x','y')]),c)


@pytest.mark.parametrize('rows',[
    [],[dict(better='a',worse='b',intask_split='test')],
    [dict(better='a',worse='a',intask_split='train')],
    as_rows([('a','b'),('b','a')])])
def test_unsafe_pair_inputs_rejected(rows):
    with pytest.raises(ValueError): pairs(rows)


def test_duplicate_card_rejected():
    _,_,c=fixture(); c['r2'].append(c['r1'][0])
    with pytest.raises(ValueError): project(c)


@pytest.mark.parametrize('edges',[
    [],[('a','b')],[('a','b'),('b','c'),('a','c')],
    [('a','b'),('c','d')],[('a','b'),('a','c'),('a','d'),('a','e')]])
def test_graph_and_visit_accounting(edges):
    assert graph(edges)==inventory(edges)[1]
    assert exposure(edges)['endpoint_visits']==2*len(edges)


def test_outside_boundary_and_cross_task_are_not_rescued():
    l,g,c=fixture(); c['r1'].append(dict(id='q',task={'name':'t2'}))
    r,t=project(c); g=g+[('a','q')]
    a=analyze(l,g,r,t)
    assert a['source_exclusions']['cross_task_pair']==1
    assert a['source_exclusions']['outside_local_train_run_boundary']==1
    assert a==recompute(as_rows(l),as_rows(g),c)
