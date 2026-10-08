import unittest
from neural_timing_diagnostic import host_gaps, source_hints


class TimingTests(unittest.TestCase):
    def test_decomposition(self):
        r=host_gaps([dict(start=1,end=2),dict(start=4,end=4.5)])
        self.assertEqual(r['host_calls']['total'],1.5)
        self.assertEqual(r['between_host_calls']['total'],2)
        self.assertEqual(r['optimizer_envelope_seconds'],3.5)
        self.assertTrue(r['not_GPU_kernel_or_CPU_stall_measurement'])

    def test_invalid(self):
        for rows in ([],[dict(start=2,end=1)],
                     [dict(start=1,end=3),dict(start=2,end=4)]):
            with self.assertRaises(ValueError):host_gaps(rows)

    def test_hints_do_not_execute_source(self):
        r=source_hints('raise RuntimeError()\ntorch.set_num_threads(3)\nf(num_workers=2)')
        self.assertEqual(r['literal_resource_hints'],[('num_workers',2)])
        self.assertEqual(r['calls'],[dict(name='torch.set_num_threads',args=[3])])


if __name__=='__main__':unittest.main()
