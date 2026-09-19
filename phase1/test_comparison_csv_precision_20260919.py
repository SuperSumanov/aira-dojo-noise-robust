import csv,io,unittest
from unittest.mock import patch
from readout_comparison_online_continuation_20260919 import read_metric_frame
from readout_comparison_pizza_online_20260919 import rank_auc

class CsvPrecision(unittest.TestCase):
    def test_explicit_precision_matches_official_contract(self):
        import types,sys
        fake=types.SimpleNamespace(read_csv=lambda path,**kwargs:(path,kwargs))
        with patch.dict(sys.modules,{'pandas':fake}):
            self.assertEqual(read_metric_frame('example.csv'),('example.csv',{'float_precision':'round_trip'}))

    def test_near_tie_is_not_a_tie(self):
        text='label,score\n0,0.5\n1,0.5000000000000001\n'
        rows=list(csv.DictReader(io.StringIO(text)))
        scores=[float(r['score']) for r in rows]
        self.assertEqual(rank_auc([int(r['label']) for r in rows],scores),1.)
        self.assertEqual(rank_auc([0,1],[round(x,15) for x in scores]),.5)

if __name__=='__main__':unittest.main()
