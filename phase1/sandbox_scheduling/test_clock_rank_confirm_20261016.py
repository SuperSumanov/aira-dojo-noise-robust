import copy
import unittest
from datetime import datetime,timezone
import clock_rank_confirm_20261016 as c

class Confirmation(unittest.TestCase):
    def setUp(self):
        self.s=dict(structure=True,complete=16,valid=16,recomputed=16,
            overlaps=[dict(host_training_envelope_overlap_seconds=1)]*4,
            ranking=[dict(strict_repeated_flip=False),dict(strict_repeated_flip=True)])
    def test_gate(self):self.assertTrue(c.eligible(self.s))
    def test_failures(self):
        for key,val in [('structure',False),('complete',15),('valid',15),('recomputed',15),
            ('overlaps',[]),('overlaps',[dict(host_training_envelope_overlap_seconds=None)]*4),
            ('ranking',[dict(strict_repeated_flip=False)]*2)]:
            s=copy.deepcopy(self.s);s[key]=val;self.assertFalse(c.eligible(s),key)
    def test_configuration_and_matrix(self):
        c.configure();self.assertEqual(c.base.D,c.D);self.assertEqual(c.base.R,c.R)
        self.assertEqual(c.base.PIN,c.PIN);self.assertEqual(c.base.NAME,c.NAME)
        self.assertEqual(c.rank.NAME,c.NAME);self.assertEqual(len(c.base.schedule()),16)
        self.assertEqual([c.rank.groups(b) for b in range(4)],[[[0],[1],[2],[3]],[[4,5],[6,7]],[[11,10],[9,8]],[[15],[14],[13],[12]]])
        self.assertEqual([c.base.gateway_port('18830',i) for i in range(4)],[42660,42661,42660,42661])
        self.assertEqual(datetime.fromtimestamp(c.WINDOW_END,timezone.utc).isoformat(),'2026-10-16T09:18:00+00:00')
    def test_shared_statistic_identity(self):
        import clock_rank_readout_20261016 as old
        import clock_rank_confirm_readout_20261016 as new
        self.assertIs(new.ranking,old.ranking)
    def test_namespace_source_is_identical(self):
        import ast
        from pathlib import Path
        folder=Path(__file__).parent
        get=lambda name:next(n for n in ast.parse((folder/name).read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='namespace_command')
        self.assertEqual(ast.dump(get('pooling_trial_20261015.py'),include_attributes=False),
            ast.dump(get('colocation_trial_20261016.py'),include_attributes=False))
    def test_real_runtime_import_path(self):
        import ast
        from pathlib import Path
        tree=ast.parse(Path(c.__file__).read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='task_runtime')
        names=[n.module for n in ast.walk(fn) if isinstance(n,ast.ImportFrom)]
        self.assertIn('colocation_trial_20261016',names)
        self.assertNotIn('pooling_trial_20261015',names)

if __name__=='__main__':unittest.main()
