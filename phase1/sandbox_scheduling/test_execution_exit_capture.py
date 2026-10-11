import ast,inspect,unittest
import execution_exit_capture_20261011 as e

class Tests(unittest.TestCase):
    def test_ten_serial_original_workers(self):
        self.assertEqual(len(e.s.schedule()),10)
        self.assertTrue(all(x['width']==1 and x['program']==1 for x in e.s.schedule()))
        source=inspect.getsource(e.worker)
        self.assertIn('return m.worker(index)',source)
        self.assertNotIn('stack_executor',source)
        self.assertNotIn('execute_code(',source)
    def test_only_cli_child_observer(self):
        ast.parse(e.SITE)
        self.assertIn("=='jupyter-kernelgateway'",e.SITE)
        self.assertNotIn('faulthandler',e.SITE)

if __name__=='__main__':unittest.main()
