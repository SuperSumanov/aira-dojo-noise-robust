"""Synthetic transport tests only; no kernel/GPU or experimental re-execution."""
import ast
import json
from pathlib import Path
import unittest
from bounded_readiness import wait_for_ready


class Transport:
    def __init__(self, deliveries=(), reply_on_send=None):
        self.now = 0.0
        self.deliveries = list(deliveries)
        self.reply_on_send = reply_on_send
        self.requests = []
        self.timeouts = []

    def clock(self):
        return self.now

    def _send_message(self, **kwargs):
        assert kwargs == dict(content={}, channel='shell', message_type='kernel_info_request')
        identity = 'request-' + str(len(self.requests) + 1)
        self.requests.append((self.now, identity))
        if len(self.requests) == self.reply_on_send:
            self.deliveries.append((self.now + .1, reply(identity)))
            self.deliveries.sort(key=lambda x: x[0])
        return identity

    def _receive_message(self, timeout_seconds):
        assert timeout_seconds > 0
        self.timeouts.append(timeout_seconds)
        if self.deliveries and self.deliveries[0][0] < self.now + timeout_seconds:
            self.now, message = self.deliveries.pop(0)
            return message
        self.now += timeout_seconds
        return None


def reply(identity):
    return dict(msg_type='kernel_info_reply', parent_header=dict(msg_id=identity))


class ReadinessTests(unittest.TestCase):
    @staticmethod
    def original_method():
        # Exact method from the credential-screened, closed 17021 source.
        fixture=Path(__file__).parent/'overlap_retry_v2_closed/readiness_evidence.json'
        evidence=json.loads(fixture.read_text())
        if evidence['client_source_sha256']!='a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf':
            raise ValueError('wrong reference source')
        source=next(v['source'] for v in evidence['client_methods'] if v['name']=='wait_for_ready')
        tree=ast.parse(source)
        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):
            raise ValueError('reference method shape')
        namespace={}
        exec(compile(tree,'<closed-17021-readiness-method>','exec'),namespace)
        return namespace['wait_for_ready']

    def test_original_single_request_cannot_recover_missing_first_reply(self):
        client=Transport(reply_on_send=2)
        self.assertFalse(self.original_method()(client,2.5))
        self.assertEqual(len(client.requests),1)
        new=Transport(reply_on_send=2)
        self.assertTrue(wait_for_ready(new,2.5,clock=new.clock))

    def test_original_timeout_can_be_extended_by_unrelated_messages(self):
        messages=[(i/10,reply('unrelated')) for i in range(1,101)]
        client=Transport(messages)
        self.assertFalse(self.original_method()(client,2.5))
        self.assertEqual(client.now,12.5)
        new=Transport(messages)
        self.assertFalse(wait_for_ready(new,2.5,clock=new.clock))
        self.assertEqual(new.now,2.5)

    def test_first_reply(self):
        client = Transport(reply_on_send=1)
        self.assertTrue(wait_for_ready(client, 5, clock=client.clock))
        self.assertEqual(len(client.requests), 1)

    def test_silent_first_request_only_repeats_info_not_code(self):
        client = Transport(reply_on_send=2)
        self.assertTrue(wait_for_ready(client, 5, clock=client.clock))
        self.assertEqual(len(client.requests), 2)

    def test_late_previous_info_reply_remains_valid(self):
        client = Transport([(1.5, reply('request-1'))])
        self.assertTrue(wait_for_ready(client, 5, clock=client.clock))
        self.assertEqual(len(client.requests), 2)

    def test_no_reply_has_fixed_total_deadline_and_send_bound(self):
        client = Transport()
        self.assertFalse(wait_for_ready(client, 2.5, clock=client.clock))
        self.assertEqual(client.now, 2.5)
        self.assertEqual(len(client.requests), 3)

    def test_unrelated_messages_do_not_reset_deadline(self):
        client = Transport([(i/10, reply('unrelated')) for i in range(1, 101)])
        self.assertFalse(wait_for_ready(client, 2.5, clock=client.clock))
        self.assertEqual(client.now, 2.5)
        self.assertEqual(len(client.requests), 3)

    def test_malformed_or_wrong_type_message_is_not_success(self):
        client = Transport([(0.1, {}),(.2, dict(parent_header=[])),
                            (.3,dict(msg_type='stream',parent_header=dict(msg_id='request-1')))])
        self.assertFalse(wait_for_ready(client, 1, clock=client.clock))

    def test_header_message_type(self):
        message = dict(header=dict(msg_type='kernel_info_reply'),
                       parent_header=dict(msg_id='request-1'))
        client = Transport([(.2,message)])
        self.assertTrue(wait_for_ready(client, 1, clock=client.clock))

    def test_transport_error_is_not_suppressed(self):
        client = Transport()
        def failed(**kwargs):
            raise ConnectionError('synthetic transport failure')
        client._send_message = failed
        with self.assertRaises(ConnectionError):
            wait_for_ready(client, 1, clock=client.clock)

    def test_invalid_limits(self):
        for timeout in (None, 0, -1, float('inf'), float('nan')):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                wait_for_ready(Transport(), timeout)
        for retry in (0, -1, float('inf'),float('nan')):
            with self.subTest(retry=retry), self.assertRaises(ValueError):
                wait_for_ready(Transport(), 1, retry_seconds=retry)


if __name__ == '__main__':
    unittest.main()
