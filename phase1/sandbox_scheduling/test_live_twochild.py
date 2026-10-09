import ast
import unittest
import live_twochild_20261010 as s


class TwoChildTests(unittest.TestCase):
    def test_paired_seeds_and_abba(self):
        rows=s.t.schedule();self.assertEqual(len(rows),16)
        self.assertEqual([rows[b*4]['arm'] for b in range(4)],['pipeline','share2','share2','pipeline'])
        for rep in range(2):
            for slot in range(4):
                pair=[r for r in rows if r['repeat']==rep and r['slot']==slot]
                self.assertEqual(len({r['seed'] for r in pair}),1)
                self.assertEqual(len({r['task'] for r in pair}),1)
    def test_common_scope(self):
        self.assertEqual(s.t.CAP,9600);self.assertEqual(s.t.FIXED_BLOCK_SECONDS,2300)
        self.assertFalse(s.t.GENERATOR_ELIGIBILITY_GATE)
        self.assertTrue(s.t.PHYSICAL_CPU_BINDING)
        self.assertLess(4*s.t.FIXED_BLOCK_SECONDS,s.t.CAP)
    def test_actual_compiled_deadlines(self):
        self.assertIn(1590,s.t.run_one.__code__.co_consts)
        self.assertIn(1590,s.t.controller.__code__.co_consts)
        self.assertIn(1700,s.t.controller.__code__.co_consts)
        self.assertIn(1500,s.t.cpu.__code__.co_consts)
        self.assertIn(2,s.t.cpu.__code__.co_consts)
    def test_no_silent_interface_change(self):
        with self.assertRaises(ValueError):s.transform('new interface','missing','replacement')
    def test_same_scientific_configs(self):
        a={'id':'a','metadata':{},'logger':{},'solver':{'num_children':2,'time_limit_secs':1500,'checkpoint_path':'x'},'task':{'results_output_dir':'x'},'interpreter':{'working_dir':'x'}}
        b={'id':'b','metadata':{},'logger':{},'solver':{'num_children':2,'time_limit_secs':1500,'checkpoint_path':'y'},'task':{'results_output_dir':'y'},'interpreter':{'working_dir':'y'}}
        self.assertEqual(s.t.scientific(a),s.t.scientific(b))
        b['solver']['num_children']=5
        self.assertNotEqual(s.t.scientific(a),s.t.scientific(b))


if __name__=='__main__':unittest.main()
