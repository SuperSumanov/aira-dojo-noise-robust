import unittest
from audit_cheap_closed_waits_20260914 import summarize
class TestWaits(unittest.TestCase):
    def test_completed_and_rejected_separate(self):
        r=summarize(b'reservation_backpressure seconds=1.5 polls=2\nreservation_backpressure seconds=2.5 polls=8\nreservation_rejected total_nusd=1 scope_nusd=2 amount_nusd=3 fresh=4 waited=5.5 permanent=True\n')
        self.assertEqual((r['logged_completed_waits'],r['logged_completed_wait_seconds'],r['logged_rejected_wait_seconds']),(2,4.,5.5))
        self.assertTrue(r['any_logged_permanent_rejection'])
    def test_no_terminal_message_does_not_invent_time(self):
        r=summarize(b'Interrupted while waiting\n')
        self.assertEqual(r['logged_completed_wait_seconds'],0)
        self.assertEqual(r['logged_rejections'],0)
if __name__=='__main__':unittest.main()
