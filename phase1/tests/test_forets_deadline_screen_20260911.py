import math
from phase1.forets_deadline_screen_20260911 import target,code_features,split_indices

def test_deadline_boundary_and_failures():
    assert target(dict(exec_time=300,exit_code=0))[0]==(1,1)
    assert target(dict(exec_time=300.01,exit_code=0))[0]==(0,1)
    assert target(dict(exec_time=1,exit_code=1))[0]==(0,0)
    for t in (None,0,-1,math.nan,math.inf,True): assert target(dict(exec_time=t,exit_code=0))[0] is None
    assert target(dict(exec_time=1,exit_code=None))[0] is None
    assert target(dict(exec_time=1,exit_code=False))[0] is None

def test_features_ignore_comments_in_ast_hash_and_never_take_outcomes():
    f,h=code_features('x=1\n')
    g,i=code_features('# comment\nx = 1\n')
    assert h==i and f['log_chars']!=g['log_chars']
    assert 'exec_time' not in f and 'exit_code' not in f
    assert code_features('this is invalid Python!')[0]['syntax_error']==1

def test_component_split_and_both_code_purges():
    rows=[dict(task='a',component='c1',code_sha='x',ast_sha='u'),
          dict(task='a',component='c2',code_sha='x',ast_sha='v'),
          dict(task='a',component='c3',code_sha='z',ast_sha='u'),
          dict(task='a',component='c3',code_sha='q',ast_sha='w'),
          dict(task='b',component='c4',code_sha='j',ast_sha='k')]
    assert split_indices(rows,'a','c1')==([3],[0])

def test_target_ignores_numeric_grades():
    x=dict(exec_time=12,exit_code=0,metric={'value':999})
    y=dict(exec_time=12,exit_code=0,metric={'value':-999})
    assert target(x)==target(y)==((1,1),None)
