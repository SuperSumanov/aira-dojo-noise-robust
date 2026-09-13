import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_forets_memory_control_20260913 as b
from forets_execution_memory_20260913 import frozen_memory,OPERATORS
from forets_single_proposal_control_20260913 import difference_paths
import derive_memory_control_tools_20260913 as derive
import tempfile

class MemoryControlTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'results/forets_reference_s32_s33_20260913'
        self.memory=frozen_memory(root/'closed-error-families.json',root/'closed-error-recurrence.json')
        self.cfg={'solver':dict(execution_timeout=300,selection_policy='uniform_random',num_children=2,num_children_to_choose=2,
            time_limit_secs=600,action_delivery_protocol='original_search_visible_action_delivery_v1',
            operators={k:{'system_message_prompt_template':{'template':'Original '+k}} for k in (*OPERATORS,'analyze')})}
    def test_matrix_and_only_prompt_changes(self):
        self.assertEqual(len(b.order()),8);self.assertEqual(len(set(b.order())),8)
        self.assertEqual(b.order()[0],(1,'leaf-classification',40,'no_memory'))
        self.assertEqual(b.order()[4],(2,'leaf-classification',41,'execution_memory'))
        with patch.object(b,'MEMORY',self.memory):
            a=b.config_transform(self.cfg,'no_memory');c=b.config_transform(self.cfg,'execution_memory')
            self.assertEqual(difference_paths(a,c),{('solver','operators',k,'system_message_prompt_template','template') for k in OPERATORS})
            identity=lambda cfg,**kw:cfg
            self.assertEqual(b.normalized_template(a,'fixture',Path('fixture'),identity),b.normalized_template(c,'fixture',Path('fixture'),identity))
    def test_deployed_algorithm_source_unchanged(self):
        with patch.object(b,'BASE','cda5e378046811fa20eadc7bc9a0d2343e69ddca'),patch.object(b,'FACTS',dict(billing_counts=[1475,5747501366,4347501366,2])),patch.object(b,'AUTH_PARENT','fixture'):
            sources=b.changed_sources()
        self.assertEqual(list(sources),[b.PREFIX+'paid_budget.py'])
        for name,raw in sources.items():compile(raw,name,'exec')
    def test_generated_reader_counts_task_orientations(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'tools';derive.derive(out,'cda5e378046811fa20eadc7bc9a0d2343e69ddca')
            spec=importlib.util.spec_from_file_location('memory_reader_fixture',out/'readout_forets_memory_control_20260913.py')
            r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
            self.assertEqual(r.SEEDS,(40,41));self.assertEqual(len(r.FILES),6)
            rows=[dict(task=t,seed=s,arm=a,technical_eligible=True,action_valid=True,iteration_valid=True,
                action_score=.6 if a=='no_memory' else .5,iteration_score=.6,api_cost_usd=.1)
                for t in r.TASKS for s in r.SEEDS for a in r.ARMS]
            result=r.paired_effects(rows)
            self.assertEqual([g['wins'] for g in result['groups']],[2,0,0,0])
            self.assertEqual([g['losses'] for g in result['groups']],[0,2,0,0])
            self.assertIn('memory_valid',result['pairs'][0]);self.assertIn('control_valid',result['pairs'][0])
            rows[0]['technical_eligible']=False
            self.assertIsNone(r.paired_effects(rows)['pairs'][0]['memory_oriented_gain'])

if __name__=='__main__':unittest.main()
