"""Regression tests: protocol plumbing only, no ML or effect claims."""
import ast, copy, unittest
from pathlib import Path
from unittest.mock import patch
from implementation_reset_contract_v2_20261005 import *

class ContractTests(unittest.TestCase):
    def test_source_programs_parse_and_satisfy_static_family(self):
        for task in TASKS:
            for p in [BASELINE] + hpo_configs(33):
                code=source_program(task,31,p);ast.parse(code)
                self.assertTrue(family_screen(code)['pass'])
                self.assertFalse(family_screen(code)['semantic_verified'])

    def test_aliases(self):
        code='''from sklearn.feature_extraction.text import TfidfVectorizer as V
from sklearn.linear_model import LogisticRegression as LR
v=V(); x=v.fit_transform(text); m=LR(); m.fit(x,y); m.predict_proba(x)'''
        self.assertTrue(family_screen(code)['pass'])
        self.assertFalse(family_screen(code.replace('v=V()',"v=V(analyzer='char')"))['pass'])
        self.assertFalse(family_screen(code+'\nfrom xgboost import XGBClassifier')['pass'])
        self.assertFalse(family_screen(code+'\nfrom sklearn.naive_bayes import MultinomialNB')['pass'])
        self.assertFalse(family_screen(code+'\nexec(raw)')['pass'])

    def test_modules_and_dynamic_analyzer(self):
        code='''import sklearn.feature_extraction.text as text
import sklearn.linear_model as lm
v=text.TfidfVectorizer();x=v.fit_transform(a);m=lm.LogisticRegression();m.fit(x,y);m.predict_proba(x)'''
        self.assertTrue(family_screen(code)['pass'])
        for suffix in ('analyzer=choice','**options',"analyzer='char_wb'"):
            self.assertFalse(family_screen(code.replace('text.TfidfVectorizer()',f'text.TfidfVectorizer({suffix})'))['pass'])

    def test_templates_replace_conflicting_prompts_without_model_change(self):
        cfg={'system_message_prompt_template':{'template':'old','input_variables':['stale']},
             'init_user_message_prompt_template':{'template':'USE 5-FOLD; DIFFERENT ASPECT','input_variables':[]},
             'llm':{'client':{'model_id':'fixed'},'generation_kwargs':{'temperature':.6,'max_tokens':8192}}}
        original=copy.deepcopy(cfg)
        for arm in ARMS[:3]:
            for kind in USER:
                out=operator_config(cfg,arm,kind)
                self.assertEqual(out['llm'],cfg['llm'])
                self.assertEqual(out['system_message_prompt_template']['input_variables'],[])
                text=out['init_user_message_prompt_template']['template']
                self.assertNotIn('USE 5-FOLD',text)
                self.assertNotIn('DIFFERENT ASPECT',text)
                self.assertEqual('prev_code' in text,kind=='improve')
                self.assertEqual('prev_buggy_code' in text,kind=='debug')
        self.assertEqual(cfg,original)
        self.assertIn('correct\nthat violation',system_prompt('continue','debug'))
        self.assertIn('NOT your required method',system_prompt('new_idea','draft'))
        with self.assertRaises(ValueError):system_prompt('random_hpo','draft')

    def test_timeout_not_arbitrary_failure(self):
        self.assertEqual(generation_failure(TimeoutError()),'bounded_generation_timeout')
        self.assertEqual(generation_failure(RuntimeError('bounded API attempt failed: TimeoutError')),'bounded_generation_timeout')
        for exc in [RuntimeError('CUDA OOM'),ValueError('bounded API attempt failed: TimeoutError'),
                    RuntimeError('bounded API attempt failed: AuthenticationError')]:
            self.assertIsNone(generation_failure(exc))

    def test_schedule_complete_balanced_and_execution_seeds_fixed(self):
        rows=schedule();self.assertEqual(len(rows),16)
        self.assertEqual(len({x['index'] for x in rows}),16)
        for t,task in enumerate(TASKS):
            group=[x for x in rows if x['task']==task]
            self.assertEqual({x['execution_seed'] for x in group},{111401+t})
            for seed in {x['seed'] for x in group}:
                self.assertEqual({x['arm'] for x in group if x['seed']==seed},set(ARMS))
        self.assertEqual([rows[2*j]['arm'] for j in range(4)],list(ARMS))
        self.assertEqual([rows[8+2*j]['arm'] for j in range(4)],list(reversed(ARMS)))

    def test_hpo_reproducibility_unique_and_randomness_local(self):
        random.seed(77);state=random.getstate()
        a=hpo_configs(81);b=hpo_configs(81)
        self.assertEqual(a,b);self.assertEqual(state,random.getstate())
        self.assertNotEqual(a,hpo_configs(82))
        self.assertEqual(len({tuple(sorted(x.items())) for x in a}),len(a))

    def test_missing_and_zero_are_not_positive(self):
        self.assertEqual(decision([]),'incomplete')
        row={'complete':True,**{'reimplement_minus_'+k:0 for k in ('continue','new_idea','random_hpo')}}
        self.assertEqual(decision([row]*4),'no_consistent_advantage_under_this_protocol')
        for k in ('continue','new_idea','random_hpo'):row['reimplement_minus_'+k]=1
        self.assertTrue(decision([row]*4).startswith('numerical_signal'))

    def test_real_host_adapter_uses_all_eighteen_assignments(self):
        import implementation_reset_v2_20261005 as runner
        with patch.object(runner,'OLD',Path(__file__).parent):
            host=runner.host()
        self.assertEqual(len(host.schedule()),18)
        self.assertEqual(sorted({s['wave'] for s in host.schedule()}),list(range(9)))
        self.assertEqual(sum(s['arm']=='ROOT' for s in host.schedule()),2)
        self.assertIs(host.freeze_sources,runner.freeze_sources)
        self.assertEqual(host.__file__,str(runner.R/runner.NAME))
        self.assertEqual(host.CAP,7200)
        self.assertIn('episode-[0-9]+',host.task_runtime.__code__.co_consts)
        self.assertIn(9,host.controller.__code__.co_consts)

if __name__=='__main__':unittest.main(verbosity=2)
