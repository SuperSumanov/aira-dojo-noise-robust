import ast
from pathlib import Path
import tarfile
import unittest
from forets_repeat_build_20260912 import order, derive


class RepeatBuildTests(unittest.TestCase):
    def test_full_matrix_reverses_order_without_dropping_failed_task(self):
        self.assertEqual(order(),[('leaf-classification','uniform_random'),
            ('leaf-classification','critic_topk_random'),('spaceship-titanic','critic_topk_random'),
            ('spaceship-titanic','uniform_random')])

    def test_real_controller_reader_and_route_can_be_derived(self):
        path=Path(__file__).parent/'releases/forets-review-20260912/release-code-capsule.tar.gz'
        with tarfile.open(path) as archive:
            for name,expected in [('forets_block_controller_20260911.py','enumerate((12,), 1)'),
                    ('forets_block_readout_20260911.py','for seed in (12,):'),
                    ('forets_paid_route_20260911.py',"FORETS_PAID_SCOPE='route_s12'")]:
                source=archive.extractfile('code/'+name).read().decode()
                changed=derive(name,source);ast.parse(changed)
                self.assertIn(expected,changed)
                with self.assertRaises(ValueError):derive(name,changed)


if __name__=='__main__':unittest.main()
