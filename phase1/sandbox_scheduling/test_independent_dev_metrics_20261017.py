import csv
import math
from pathlib import Path
import tempfile
import unittest
import independent_dev_metrics_20261017 as m

TEST_TEMP = Path(__file__).resolve().parents[2]/'_codex_tmp'


class Metrics(unittest.TestCase):
    def test_auc_ties(self):
        self.assertEqual(m.auc_pairs([(.5, 0), (.5, 1)]), .5)
        self.assertEqual(m.auc_pairs([(.1, 0), (.9, 1)]), 1)
        self.assertEqual(m.auc_pairs([(.9, 0), (.1, 1)]), 0)
        pairs = [(.2, 1), (.2, 0), (.5, 0), (.9, 1), (.9, 0)]
        pos = [p for p, y in pairs if y]; neg = [p for p, y in pairs if not y]
        brute = sum((p > n) + .5*(p == n) for p in pos for n in neg)/(len(pos)*len(neg))
        self.assertEqual(m.auc_pairs(pairs), brute)

    def test_id_alignment_and_duplicate(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            d = Path(d); ref = d/'ref.csv'; pred = d/'pred.csv'
            ref.write_text('id,has_cactus\na,0\nb,1\nc,0\n')
            pred.write_text('id,has_cactus\nb,0.9\nc,0.2\na,0.1\n')
            self.assertEqual(m.aerial(ref, pred), (1, 3))
            pred.write_text('id,has_cactus\nb,0.9\nb,0.2\na,0.1\n')
            with self.assertRaises(ValueError): m.aerial(ref, pred)

    def test_pixel_addressing(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'x.csv'; images = {'7': (2, 2, bytes([0, 255, 128, 64]))}
            with p.open('w', newline='') as f:
                w = csv.writer(f); w.writerow(['id', 'value'])
                w.writerows([('7_2_2', 64/255), ('7_1_2', 1), ('7_2_1', 128/255), ('7_1_1', 0)])
            self.assertEqual(m.denoise(images, p), (0, 4))
            p.write_text('id,value\n7_1_1,1\n7_1_2,1\n7_2_1,0\n7_2_2,0\n')
            self.assertAlmostEqual(m.denoise(images, p)[0], math.sqrt((1+(128/255)**2+(64/255)**2)/4))

    def test_pixel_rejections(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as d:
            p = Path(d)/'x.csv'; images = {'1': (1, 1, bytes([0]))}
            for body in ('1_1_1,0\n1_1_1,0\n', '1_1_2,0\n', '1_1_1,nan\n', '', '01_1_1,0\n', '1_1_1,2\n'):
                p.write_text('id,value\n'+body)
                with self.assertRaises(ValueError): m.denoise(images, p)


if __name__ == '__main__': unittest.main()
