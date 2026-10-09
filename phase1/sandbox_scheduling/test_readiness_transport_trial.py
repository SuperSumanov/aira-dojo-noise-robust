from collections import Counter
import unittest
from readiness_transport_trial import Observer,schedule
from bounded_readiness import wait_for_ready
from test_bounded_readiness import Transport


class TransportTrialTests(unittest.TestCase):
    def test_fixed48_counterbalance_and_no_source_programs(self):
        rows=schedule()
        self.assertEqual([r['index'] for r in rows],list(range(48)))
        self.assertEqual(Counter(r['arm'] for r in rows),dict(serial=24,parallel4=24))
        for b in range(12):
            own=rows[4*b:4*b+4]
            self.assertEqual(len({r['arm'] for r in own}),1)
            self.assertEqual([r['position'] for r in own],list(range(4)))
        for repeat in range(6):
            self.assertEqual({r['arm'] for r in rows if r['repeat']==repeat},{'serial','parallel4'})

    def test_observer_preserves_same_helper_behavior(self):
        for respond in (1,2,None):
            reference=Transport(reply_on_send=respond);observed=Transport(reply_on_send=respond)
            proxy=Observer(observed)
            self.assertEqual(wait_for_ready(reference,3,clock=reference.clock),
                             wait_for_ready(proxy,3,clock=observed.clock))
            self.assertEqual(reference.requests,observed.requests)
            self.assertEqual(reference.timeouts,observed.timeouts)
            self.assertEqual(proxy.counts['sent_info'],len(observed.requests))
            self.assertEqual(proxy.counts['matched_info_reply'],0 if respond is None else 1)

    def test_malformed_input_is_passed_through_not_published(self):
        message=dict(msg_type='private-unknown',parent_header=dict(msg_id=[]),content='private payload')
        client=Transport([(0.1,message)]);observer=Observer(client)
        self.assertFalse(wait_for_ready(observer,1,clock=client.clock))
        self.assertEqual(observer.counts['received_other'],1)
        self.assertNotIn('private',str(observer.state()))

    def test_non_info_request_is_forbidden(self):
        with self.assertRaises(ValueError):
            Observer(Transport())._send_message(content={'code':'pass'},channel='shell',message_type='execute_request')


if __name__=='__main__':unittest.main()
