import copy,unittest
from unittest.mock import patch
import run_comparison_pizza_prefix_20260919 as driver

class SelectedSecond(unittest.TestCase):
    def test_fixed_original_order_not_score(self):
        nodes=[dict(run='r',group='executed',parents=[0],operators_used=['draft'],step=step,id=str(step),score=score) for step,score in ((4,-9),(1,999))]
        with patch.object(driver,'SELECT_SECOND',True):
            self.assertEqual(driver.select_fixed_node(nodes,'r')['id'],'4')
            changed=copy.deepcopy(nodes);changed[0]['score']=float('nan')
            self.assertEqual(driver.select_fixed_node(changed,'r')['id'],'4')
    def test_old_prefix_still_first(self):
        nodes=[dict(run='r',group='executed',parents=[0],operators_used=['draft'],step=i,id=str(i)) for i in (1,3)]
        with patch.object(driver,'SELECT_SECOND',False):self.assertEqual(driver.select_fixed_node(nodes,'r')['id'],'1')
    def test_incomplete_pool_fails(self):
        with self.assertRaises(ValueError):driver.select_fixed_node([],'r')

if __name__=='__main__':unittest.main()
