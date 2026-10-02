"""Zero-network, no-fit arithmetic tests. Run directly with standard Python."""
import ast,math,pathlib,runpy
base=pathlib.Path(__file__).resolve().parents[1]/'scripts'
for name in ('state_feedback_readout_20261002.py','state_feedback_verify_20261002.py'):
    ast.parse((base/name).read_text())
r=runpy.run_path(str(base/'state_feedback_readout_20261002.py'))
rows=[dict(seed=s,arm=a,initial=.5,gain=g) for s in (1,2) for a,g in zip('ABCD',(0,.01,.02,.08))]
p,stats,gate=r['contrasts'](rows)
assert gate and math.isclose(stats['interaction']['median'],.05) and stats['interaction']['sample_variance']==0
for row in rows:row['gain']=0
assert not r['contrasts'](rows)[2]
rows[0]['initial']=None;rows[0]['gain']=None
assert r['contrasts'](rows)[1]['interaction']['n']==1 and not r['contrasts'](rows)[2]
v=runpy.run_path(str(base/'state_feedback_verify_20261002.py'))
y={'a':{'requester_received_pizza':'1'},'b':{'requester_received_pizza':'0'}}
for pred,expected in [({'a':.8,'b':.1},1),({'a':.1,'b':.8},0),({'a':.5,'b':.5},.5)]:
    assert v['auc'](y,pred)==expected
print('PASS contrast direction, null, missingness and independent AUC algebra; no network or model calls')
