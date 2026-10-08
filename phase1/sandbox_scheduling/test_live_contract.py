import math
import unittest
from live_runtime_hooks import corrected_seconds
from live_search_trial_20261009 import schedule, replace_once, scientific


class ContractTests(unittest.TestCase):
    def test_matrix_and_pairing(self):
        rows=schedule()
        self.assertEqual(len(rows),16)
        self.assertEqual([rows[i]['arm'] for i in (0,4,8,12)],['pipeline','share2','share2','pipeline'])
        for rep in range(2):
            for slot in range(4):
                a,b=rows[8*rep+slot],rows[8*rep+4+slot]
                for key in ('seed','task','repeat','slot'):self.assertEqual(a[key],b[key])
        self.assertEqual(len({(r['task'],r['seed']) for r in rows}),8)

    def test_exact_insertion(self):
        self.assertEqual(replace_once('abc','b','X'),'aXc')
        for value in ('ac','abbc'):
            with self.assertRaises(ValueError):replace_once(value,'b','X')

    def test_queue_timing(self):
        self.assertEqual(corrected_seconds(5,3),2)
        for args in ((-1,0),(2,3),(2,-1),(math.nan,1),(2,math.inf)):
            with self.assertRaises(ValueError):corrected_seconds(*args)

    def test_scientific_normalization_keeps_budget(self):
        cfg={'id':'x','metadata':{'seed':1},'logger':{},
             'solver':{'checkpoint_path':'x','time_limit_secs':600},
             'task':{'results_output_dir':'x','name':'pizza'},
             'interpreter':{'working_dir':'x','timeout':240}}
        cleaned=scientific(cfg)
        self.assertEqual(cleaned['solver']['time_limit_secs'],600)
        self.assertEqual(cleaned['interpreter']['timeout'],240)
        self.assertIn('checkpoint_path',cfg['solver'])

if __name__=='__main__':unittest.main()
