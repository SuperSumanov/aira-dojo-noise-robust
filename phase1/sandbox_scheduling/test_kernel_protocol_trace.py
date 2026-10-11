import ast
from pathlib import Path
import unittest
from kernel_protocol_trace_20261011 import direct_counter, observer_class


class TraceTests(unittest.TestCase):
    def test_direct_entry_only(self):
        source=Path(__file__).with_name('gateway_counter.py').read_text()
        result=direct_counter(source)
        self.assertNotIn("runpy.run_module('jupyter'",result)
        self.assertIn('KernelGatewayApp.launch_instance',result)
        self.assertEqual(source.split("if __name__=='__main__':")[0],result.split("if __name__=='__main__':")[0])
        compile(result,'counter','exec')

    def test_existing_observer_only_enums(self):
        Observer=observer_class(Path(__file__).with_name('readiness_transport_trial.py').read_text())
        class Client:
            def _send_message(self,**kwargs):return 'private-id'
            def _receive_message(self,seconds):return dict(header=dict(msg_type='kernel_info_reply'),parent_header=dict(msg_id='private-id'),content=dict(secret='not-exported'))
        obs=Observer(Client());obs._send_message(content={},channel='shell',message_type='kernel_info_request');obs._receive_message(1)
        state=obs.state();self.assertEqual(state['counts']['matched_info_reply'],1)
        self.assertNotIn('private-id',str(state));self.assertNotIn('not-exported',str(state))

    def test_original_single_query_not_retry(self):
        source=Path(__file__).with_name('kernel_protocol_trace_20261011.py').read_text()
        self.assertNotIn('from bounded_readiness',source)
        tree=ast.parse(source);self.assertTrue(tree)
        self.assertIn('ok=original(proxy,timeout_seconds)',source)


if __name__=='__main__':unittest.main()
