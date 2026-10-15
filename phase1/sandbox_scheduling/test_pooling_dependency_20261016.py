import unittest
from pooling_dependency_sensitivity_20261016 import chains,simulate,summary

def job(sid,arrival,start,duration,deadline=100):
    return dict(session=sid,task=sid%2,lane=sid//2,arrival=arrival,
                original_start=start,duration=duration,deadline=deadline)

class Tests(unittest.TestCase):
    def test_serial_observed_gaps(self):
        jobs=[job(0,0,2,10),job(0,20,23,5)]
        for mode in ('fixed','shared','unlimited'):
            r=simulate(jobs,mode);self.assertEqual([x['end'] for x in r],[10,23])
    def test_fixed_dependency_reconstructs_trace(self):
        jobs=[job(0,0,0,10),job(1,2,10,3),job(0,12,13,4)]
        self.assertEqual([r['end'] for r in simulate(jobs,'fixed')],[10,13,17])
    def test_shared_releases_other_gpu(self):
        jobs=[job(0,0,0,10),job(1,2,10,3),job(0,12,13,4)]
        self.assertEqual([r['end'] for r in simulate(jobs,'shared')],[10,5,16])
    def test_same_session_never_overlaps(self):
        jobs=[job(0,0,0,10),job(0,12,12,4)]
        r=simulate(jobs,'shared',5);self.assertEqual([x['end'] for x in r],[15,26])
    def test_deadline_no_validity_claim(self):
        jobs=[job(0,0,0,10,8),job(1,1,10,1,8)]
        self.assertEqual(summary(simulate(jobs,'fixed'))['released_by_deadline'],0)
        self.assertEqual(summary(simulate(jobs,'shared'))['released_by_deadline'],1)
    def test_reject_nonserial_input(self):
        with self.assertRaises(AssertionError):chains([job(0,0,0,10),job(0,5,5,10)])
    def test_zero_duration(self):
        self.assertEqual(len(simulate([job(0,0,0,0),job(1,0,0,0)],'shared')),2)
    def test_empty(self):self.assertEqual(simulate([],'shared'),[])

if __name__=='__main__':unittest.main()
