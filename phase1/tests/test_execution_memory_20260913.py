import copy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_execution_memory_20260913 import frozen_memory,apply_memory,TEXT_SHA,OPERATORS
from forets_single_proposal_control_20260913 import difference_paths

class MemoryTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'results/forets_reference_s32_s33_20260913'
        self.memory=frozen_memory(root/'closed-error-families.json',root/'closed-error-recurrence.json')
        self.cfg={'solver':dict(execution_timeout=300,selection_policy='uniform_random',num_children=2,num_children_to_choose=2,
            operators={k:{'system_message_prompt_template':{'template':'Original {task} '+k}} for k in (*OPERATORS,'analyze')})}
    def test_prior_only_text_frozen(self):
        self.assertEqual(self.memory['text_sha256'],TEXT_SHA)
        self.assertEqual(len(self.memory['errors']),3)
        self.assertFalse(self.memory['contains_scores_or_solutions'])
    def test_exact_three_template_append_and_input_unchanged(self):
        before=copy.deepcopy(self.cfg)
        off=apply_memory(self.cfg,self.memory,False);on=apply_memory(self.cfg,self.memory,True)
        self.assertEqual(off,before);self.assertEqual(self.cfg,before)
        self.assertEqual(difference_paths(off,on),{('solver','operators',k,'system_message_prompt_template','template') for k in OPERATORS})
        for k in OPERATORS:
            self.assertEqual(on['solver']['operators'][k]['system_message_prompt_template']['template'],
                off['solver']['operators'][k]['system_message_prompt_template']['template']+'\n\n'+self.memory['text'])
    def test_cannot_replace_memory_and_rehash(self):
        self.memory['text']+=' altered'
        self.memory['text_sha256']=hashlib.sha256(self.memory['text'].encode()).hexdigest()
        with self.assertRaises(ValueError):apply_memory(self.cfg,self.memory,True)
    def test_duplicate_and_wrong_selector_rejected(self):
        on=apply_memory(self.cfg,self.memory,True)
        with self.assertRaises(ValueError):apply_memory(on,self.memory,True)
        self.cfg['solver']['selection_policy']='critic_topk_random'
        with self.assertRaises(ValueError):apply_memory(self.cfg,self.memory,False)
    def test_non_boolean_and_source_substitution_rejected(self):
        with self.assertRaises(ValueError):apply_memory(self.cfg,self.memory,1)
        self.memory['taxonomy_sha256']='0'*64
        with self.assertRaises(ValueError):apply_memory(self.cfg,self.memory,True)

if __name__=='__main__':unittest.main()
