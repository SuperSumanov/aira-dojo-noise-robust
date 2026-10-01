import importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'scripts/task_feedback_public_rule_20261002.py'
sp=importlib.util.spec_from_file_location('rule',P);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
def group(value,good_train=True,good_confirm=True,n=300,c=150):
    out=[];counts={False:0,True:0};i=0
    while counts[False]<n or counts[True]<c:
        id=f'{value}-{i}';i+=1;b=m.bucket(id)==0
        if counts[b]>=(c if b else n):continue
        counts[b]+=1;good=good_confirm if b else good_train
        out.append(dict(textID=id,text='alpha beta',selected_text='alpha beta' if good else 'gamma',kind=value))
    return out
class Tests(unittest.TestCase):
    def test_good_rule_and_excluded_target(self):
        x=m.select_rule(group('good')+group('bad',False,False));self.assertEqual(x['chosen'],dict(column='kind',value='good',operation='copy_full_text'));self.assertEqual(x['features'],['kind'])
    def test_confirmation_failure_no_runner_up(self):
        x=m.select_rule(group('big',True,False,n=400)+group('small'));self.assertIsNone(x['chosen']);self.assertEqual(x['confirmation']['mean'],0)
    def test_no_mining_signal(self):self.assertIsNone(m.select_rule(group('x',False,False)+group('y',False,False))['chosen'])
    def test_minimum_count(self):self.assertIsNone(m.select_rule(group('x',n=199)+group('y',False,False))['chosen'])
    def test_permutation_invariance(self):
        data=group('x')+group('y',False,False);self.assertEqual(m.select_rule(data),m.select_rule(data[::-1]))
    def test_duplicate_id_rejected(self):
        data=group('x')+group('y');data.append(data[0])
        with self.assertRaises(AssertionError):m.select_rule(data)
if __name__=='__main__':unittest.main()
