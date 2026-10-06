import hashlib
import unittest

import census


class CensusTests(unittest.TestCase):
    def test_cpu_minus_one_in_kwargs_and_dictionary(self):
        for code in ('m=RandomForestClassifier(n_jobs=-1)', 'params={"n_jobs":-1};m=LR(**params)'):
            self.assertTrue(census.inspect(code)['flags']['all_cpu_knob'])

    def test_not_every_negative_worker_is_all_cores(self):
        self.assertFalse(census.inspect('DataLoader(x,num_workers=-1)')['flags']['all_cpu_knob'])

    def test_explicit_gpu_forms(self):
        for code in ('x=x.cuda()', 'm.to("cuda:0")', 'torch.device("cuda")',
                     'params={"device":"cuda"}', 'CatBoost(task_type="GPU")', 'XGB(tree_method="gpu_hist")'):
            self.assertTrue(census.inspect(code)['flags']['explicit_gpu_hint'], code)

    def test_conditional_gpu_is_not_measured_usage(self):
        result = census.inspect('import torch as t\ndev=t.device("cuda" if t.cuda.is_available() else "cpu")')
        self.assertTrue(result['flags']['cuda_availability_branch_hint'])
        self.assertTrue(result['flags']['gpu_backend_import'])
        self.assertNotIn('gpu_used', result)

    def test_aliases_cpu_api_and_threads(self):
        result = census.inspect('from os import cpu_count as cores\nfrom torch import set_num_threads as threads\nthreads(cores())')
        self.assertTrue(result['flags']['cpu_count_query'])
        self.assertTrue(result['flags']['thread_setter'])

    def test_comments_and_strings_not_code(self):
        result = census.inspect('# n_jobs=-1\ns="model.cuda();subprocess.run()"')
        self.assertFalse(result['flags']['all_cpu_knob'])
        self.assertFalse(result['flags']['explicit_gpu_hint'])
        self.assertFalse(result['flags']['subprocess_hint'])

    def test_parse_failure_is_not_negative(self):
        result = census.inspect('def invalid:')
        self.assertFalse(result['parsed'])
        self.assertIsNone(result['flags'])

    def test_resource_settings_fingerprint(self):
        first = census.inspect('model.fit(batch_size=32)')
        same = census.inspect('model.fit(batch_size=32)\n# only comment')
        changed = census.inspect('model.fit(batch_size=64)')
        self.assertEqual(first['resource_setting_fingerprint'], same['resource_setting_fingerprint'])
        self.assertNotEqual(first['resource_setting_fingerprint'], changed['resource_setting_fingerprint'])

    def test_no_outcome_field_access(self):
        class Guard(dict):
            def __getitem__(self, key):
                if key not in ('base_code', 'code'):
                    raise AssertionError('Forbidden field accessed')
                return super().__getitem__(key)
        pair = Guard(base_code='a=1', code='a=2', feedback=object(), score=object(), runtime=object())
        row = dict(task='task', loop='loop_0', base_sha256=hashlib.sha256(b'a=1').hexdigest(),
                   code_sha256=hashlib.sha256(b'a=2').hexdigest())
        self.assertEqual(census.get_pair({'task':{'loop_0':pair}}, row), ('a=1','a=2'))
        row['code_sha256'] = 'wrong'
        with self.assertRaises(ValueError):
            census.get_pair({'task':{'loop_0':pair}}, row)

    def test_summary_keeps_failed_denominator(self):
        rows = [dict(task='a', **census.inspect('import sklearn\nm=RF(n_jobs=-1)')),
                dict(task='a', **census.inspect('bad: :')), dict(task='b', **census.inspect('x=1'))]
        result = census.summarize(rows)
        self.assertEqual(result['programs'], 3)
        self.assertEqual(result['parsed'], 2)
        self.assertEqual(result['parse_failed'], 1)
        self.assertEqual(result['tasks'], 2)
        self.assertEqual(result['flag_counts']['all_cpu_knob'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
