import ast,inspect,unittest
import factory_integration_20261011 as d
import factory_integration_readout_20261011 as v

class Tests(unittest.TestCase):
    def test_schedule_matches_independent_readout(self):
        self.assertEqual([(r['index'],r['condition'],r['repeat']) for r in d.schedule()],v.expected())
        self.assertEqual(len(d.schedule()),6)
    def test_real_factory_entry_and_fixed_timeout(self):
        src=inspect.getsource(d.run)
        self.assertIn('JupyterInterpreterFactory(cfg',src)
        self.assertIn('timeout=450',src)
        self.assertIn('factory.close()',src)
        self.assertIn('if not row[\'accepted\']:break',src)
        self.assertIn('reset_session=True',src)
        self.assertIn('reset_session=False',src)
        ast.parse(src)
    def test_cleanup_failures_not_hidden_by_rc(self):
        for text in ('500 DELETE /api/kernels/1','InvalidStateError','Error in sitecustomize','did not terminate; sending SIGKILL'):
            self.assertTrue(any(v.flags(text).values()))
        self.assertFalse(any(v.flags('normal shutdown').values()))

if __name__=='__main__':unittest.main()
