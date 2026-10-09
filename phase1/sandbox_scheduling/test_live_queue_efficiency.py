import unittest
from live_queue_efficiency import account


def event(t,kind,key,a,q,w=1):
    return dict(time=t,event=kind,key=key,active=a,queued=q,limit=w)


class QueueEfficiencyTests(unittest.TestCase):
    def test_waiting_during_full_lease_not_spare_capacity(self):
        es=[event(0,'queued','a',0,1),event(.1,'admitted','a',1,0),
            event(1,'queued','b',1,1),event(11,'released','a',0,1),
            event(11.2,'admitted','b',1,0),event(12,'released','b',0,0)]
        r=account(es,1)
        self.assertAlmostEqual(r['waiting_with_spare_permit_slot_seconds'],.3)
        self.assertAlmostEqual(r['waiting_task_seconds_including_cancelled'],10.3)
        self.assertAlmostEqual(r['busy_permit_slot_seconds'],11.7)

    def test_two_free_permits_and_cancelled_wait_counted(self):
        es=[event(0,'queued','a',0,1,2),event(1,'queued','b',0,2,2),
            event(2,'admitted','a',1,1,2),event(3,'queue_cancelled','b',1,0,2),
            event(4,'released','a',0,0,2)]
        r=account(es,2)
        self.assertEqual(r['waiting_with_spare_permit_slot_seconds'],4)
        self.assertEqual(r['busy_permit_slot_seconds'],2)

    def test_no_events_is_not_measured_device_idle(self):
        self.assertEqual(account([],1)['event_span_seconds'],0)

    def test_partial_backwards_and_nonfifo_rejected(self):
        with self.assertRaises(ValueError):account([event(0,'queued','a',0,1)],1)
        with self.assertRaises(ValueError):account([event(1,'queued','a',0,1),event(0,'admitted','a',1,0)],1)
        with self.assertRaises(ValueError):account([event(0,'queued','a',0,1),event(1,'admitted','b',1,0)],1)


if __name__=='__main__':unittest.main()
