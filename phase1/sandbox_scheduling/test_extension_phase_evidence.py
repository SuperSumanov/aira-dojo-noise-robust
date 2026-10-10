import unittest
from extension_phase_evidence import interval,overlap,phase_row


class PhaseEvidenceTests(unittest.TestCase):
    def test_overlap_and_touch(self):
        self.assertEqual(overlap((0,3),(2,5)),1)
        self.assertEqual(overlap((0,3),(3,5)),0)
        self.assertEqual(overlap((0,1),(2,3)),0)
    def test_reject_bad_intervals(self):
        for pair in ((2,1),(float('nan'),2),(0,float('inf')),(True,2)):
            with self.assertRaises(ValueError):interval(*pair)
    def test_host_receipt_not_kernel_claim(self):
        calls=[dict(start=i+1.,end=i+1.5,devices=['cuda:0'],gradient_parameters=2) for i in range(150)]
        record=dict(device='cuda:0',steps=150,first_step_start=1.,last_step_end=150.5,host_step_intervals=calls)
        row=dict(index=0,program=0,repeat=0,arm='pipeline')
        value=phase_row(row,0,155,record)
        self.assertTrue(value['timing_is_host_not_kernel'])
        self.assertEqual(value['before_first_optimizer_seconds'],1)
        self.assertEqual(value['after_last_optimizer_seconds'],4.5)
        record['steps']=149
        with self.assertRaises(ValueError):phase_row(row,0,155,record)
    def test_false_device_rejected(self):
        calls=[dict(start=i+1.,end=i+1.5,devices=['cpu'],gradient_parameters=2) for i in range(150)]
        record=dict(device='cuda:0',steps=150,first_step_start=1.,last_step_end=150.5,host_step_intervals=calls)
        with self.assertRaises(ValueError):phase_row(dict(index=0,program=0,repeat=0,arm='share2'),0,155,record)


if __name__ == '__main__':unittest.main()
