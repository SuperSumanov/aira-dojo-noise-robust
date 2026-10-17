import copy
from pathlib import Path
import unittest
from unittest.mock import patch
import closed_parent_delta_20261017 as reader

def fixture():
    h=reader.m.codehash
    nodes=[dict(step=0,code='warm',operators_used=['warm_start'],parents=[]),
           dict(step=1,code='first',operators_used=['improve'],parents=[0]),
           dict(step=2,code='second',operators_used=['improve'],parents=[1])]
    task='denoising-dirty-documents';events=[dict(event='warm_start',run=0,code_sha256=h('warm'))]
    cc=[];data={}
    for i,(code,parent,ps,score,when) in enumerate((('first','warm',.1,.08,1),('second','first',.08,.06,6))):
        events.extend([dict(event='admitted',key=str(i),parent=h(parent),role='improve',time=when,
             snapshot=dict(archive={task:{h(parent):dict(metric=ps)}})),
             dict(event='parent_used',run=0,key=str(i),parent=h(parent),child=h(code))])
        cc.append(dict(index=0,candidate=i,block=0,task=task,category='improve_from_'+('warm' if i==0 else 'new'),
            valid=True,score=score,pool_elapsed=4+5*i))
        data[f'episode-0/candidate-{i}.json']=dict(code_sha256=h(code))
    data['episode-0/checkpoint/journal.jsonl']=nodes
    for b in range(4):
        data[f'generation-{b}/events.jsonl']=events if b==0 else []
        data[f'block-{b}/budget-slot.json']=dict(start=0)
    data['lineage.json']=dict(source_hashes={k:'h' for k in data},plan_sha256='h',candidates=cc,
        groups=[dict(block=0,task=task,initial=.1)])
    return data

def run(data):
    with patch.object(reader.m,'sha',return_value='h'),patch.object(reader.m,'load',side_effect=lambda p,lines=False:copy.deepcopy(data[p.relative_to('/fixture').as_posix()])):
        return reader.evaluate(Path('/fixture'),'lineage.json','h')

class ParentDelta(unittest.TestCase):
    def test_true_parent_and_prior_external_score(self):
        out=run(fixture());self.assertEqual(out['unresolved'],0)
        self.assertAlmostEqual(out['rows'][1]['gain_vs_parent'],.02)
        self.assertEqual(out['rows'][1]['parent_evidence'],'earlier_pristine_dev_return')

    def test_future_parent_refused(self):
        d=fixture();d['lineage.json']['candidates'][0]['pool_elapsed']=7
        with self.assertRaisesRegex(AssertionError,'earlier pristineDEV'):run(d)

    def test_parent_score_mismatch_refused(self):
        d=fixture();d['lineage.json']['candidates'][0]['score']=.07
        with self.assertRaisesRegex(AssertionError,'earlier pristineDEV'):run(d)

    def test_invalid_child_not_removed(self):
        d=fixture();d['lineage.json']['candidates'][1].update(valid=False,score=None)
        out=run(d);self.assertEqual(len(out['rows']),2);self.assertEqual(out['rows'][1]['relation'],'invalid')

    def test_multiple_parent_events_remain_unknown(self):
        d=fixture();d['generation-0/events.jsonl'].append(copy.deepcopy(d['generation-0/events.jsonl'][-1]))
        out=run(d);self.assertEqual(out['unresolved'],1);self.assertEqual(out['rows'][1]['reason'],'ambiguous_parent_event')

if __name__=='__main__':unittest.main()
