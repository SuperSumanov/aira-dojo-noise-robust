import ast
from concurrent.futures import Future
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PHASE = Path(__file__).resolve().parents[1]


class WireHookTests(unittest.TestCase):
    def test_pass_through_and_no_payload_or_identity_export(self):
        class Connection:
            def __init__(self):
                self.session = types.SimpleNamespace(session='fixture-client-session')
                self.calls = []
            def handle_incoming_message(self, raw):
                self.calls.append(('in', raw))
                return 'original-in-return'
            def _on_zmq_reply(self, stream, msg):
                self.calls.append(('out', stream, msg))
                return 'original-out-return'
            def connect(self):
                self.future = Future()
                return self.future
        name = 'jupyter_server.services.kernels.connection.channels'
        module = types.ModuleType(name)
        module.ZMQChannelsWebsocketConnection = Connection
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {name:module}):
            target = Path(tmp)/'trace.jsonl'
            with patch.dict(os.environ, {'KERNEL_DIAG_LOG':str(target), 'KERNEL_DIAG_TRIAL':'3'}):
                spec = importlib.util.spec_from_file_location('wire_hook_fixture', PHASE/'kernel_wire_hook_20260912.py')
                hook = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(hook)
                c = Connection()
                raw = json.dumps(dict(channel='shell', header=dict(msg_type='kernel_info_request',
                    msg_id='fixture-private-id', session='fixture-client-session'), content={'private':'MUST_NOT_APPEAR'}))
                self.assertEqual(c.handle_incoming_message(raw), 'original-in-return')
                msg = dict(msg_type='kernel_info_reply', parent_header={'msg_id':'fixture-private-id'}, content={'private':'MUST_NOT_APPEAR'})
                stream = types.SimpleNamespace(channel='shell')
                self.assertEqual(c._on_zmq_reply(stream, msg), 'original-out-return')
                self.assertIs(c.calls[-1][2], msg)
                self.assertEqual(c.calls[0][1], raw)
                future = c.connect()
                self.assertIs(future, c.future)
                future.set_result(None)
            data = target.read_text()
            for private in ('MUST_NOT_APPEAR', 'fixture-private-id', 'fixture-client-session'):
                self.assertNotIn(private, data)
            rows = [json.loads(s) for s in data.splitlines()]
            self.assertEqual(rows[1]['session_matches'], True)
            self.assertEqual(rows[2]['parent_matches'], True)
            self.assertEqual(rows[-1]['event'], 'server_connect_finished')

    def test_diagnostic_source_compiles(self):
        for name in ('kernel_wire_hook_20260912.py', 'forets_kernel_wire_20260912.py'):
            ast.parse((PHASE/name).read_text())

    def test_loaded_only_trace_is_rejected(self):
        spec = importlib.util.spec_from_file_location('wire_worker', PHASE/'forets_kernel_wire_20260912.py')
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        trace = {'event_counts': {'instrumentation_loaded': 1}}
        self.assertFalse(worker.trace_is_observable(trace, True))
        self.assertFalse(worker.trace_is_observable(trace, False))
        trace['event_counts'].update(server_connect=1, server_incoming=2)
        self.assertTrue(worker.trace_is_observable(trace, False))
        self.assertFalse(worker.trace_is_observable(trace, True))
        trace['matched_egress'] = {'shell:kernel_info_reply': 1}
        self.assertTrue(worker.trace_is_observable(trace, True))
        trace['event_counts']['instrumentation_error'] = 1
        self.assertFalse(worker.trace_is_observable(trace, True))

    def test_bootstrap_does_not_delegate_to_execing_jupyter_cli(self):
        spec = importlib.util.spec_from_file_location('wire_bootstrap', PHASE/'forets_kernel_wire_20260912.py')
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        ast.parse(worker.DIAGNOSTIC_BOOTSTRAP)
        self.assertIn("run_module('kernel_gateway'", worker.DIAGNOSTIC_BOOTSTRAP)
        self.assertNotIn("run_module('jupyter'", worker.DIAGNOSTIC_BOOTSTRAP)


if __name__=='__main__':
    unittest.main()
