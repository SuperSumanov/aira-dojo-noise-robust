import ast
from pathlib import Path
import unittest


class CounterTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(Path(__file__).with_name('gateway_counter.py').read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='message_kind')
        space={'json':__import__('json'),'TYPES':{'kernel_info_request','kernel_info_reply','status'}}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'counter','exec'),space)
        self.kind=space['message_kind']
    def test_request(self):self.assertEqual(self.kind('{"header":{"msg_type":"kernel_info_request"}}'),'kernel_info_request')
    def test_multipart_reply(self):
        self.assertEqual(self.kind([b'identity',b'<IDS|MSG>',b'signature',b'{"msg_type":"kernel_info_reply"}',b'{}']),'kernel_info_reply')
    def test_no_content_export(self):self.assertEqual(self.kind({'header':{'msg_type':'private_unknown_value'}}),'other')
    def test_invalid(self):self.assertEqual(self.kind([b'bad']),'unknown')
    def test_wrapper_contract(self):
        import readiness_gateway_trial as wrapper
        self.assertEqual(len(wrapper.trial.schedule()),48)
        self.assertEqual(wrapper.trial.NAME,'readiness_gateway_trial.py')
        self.assertIn('gateway',str(wrapper.trial.R))
        self.assertIn('gateway_counter.py',wrapper.trial.prepare.__code__.co_consts)


if __name__=='__main__':unittest.main()
