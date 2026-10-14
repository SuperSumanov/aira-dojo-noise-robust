import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import fixed_public_preview_20261014 as p


class Tests(unittest.TestCase):
    def test_reject_runtime_error_and_guard_receipts(self):
        for text in ('', 'ERROR:\nKernel did not become ready in time.',
                     'kernel-shutdown-guard-installed-random.json', 'x'*6201):
            with self.assertRaises(ValueError): p.validate_text(text)
        self.assertEqual(p.validate_text('data/\n  train/'), 'data/\n  train/')

    def test_drift_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'bundle.json'; text='data/\n  train/'
            b=dict(schema=1,native_preview_source_sha256=p.PREVIEW_SOURCE_SHA,
                   tasks={p.TASKS[0]:dict(text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest())})
            path.write_text(json.dumps(b)); pin=p.sha(path)
            self.assertEqual(p.load_text(path,pin,p.TASKS[0]),text)
            path.write_text(json.dumps(dict(b,schema=2)))
            with self.assertRaises(ValueError):p.load_text(path,pin,p.TASKS[0])

    def test_reject_before_transport_and_sticky(self):
        messages=[dict(role='user',content='public input')]; sent=[]; events=[]
        async def query(messages):sent.append(messages);return 'ok'
        guard=p.FirstRequestGuard(p.digest(messages),events.append)
        call=guard.wrap(query)
        with self.assertRaises(ValueError):asyncio.run(call([dict(role='user',content='changed history')]))
        with self.assertRaises(ValueError):asyncio.run(call(messages))
        self.assertEqual(sent,[]);self.assertEqual(len(events),1);self.assertFalse(events[0]['passed'])

    def test_only_first_request_must_match(self):
        messages=[dict(role='user',content='same public input')];sent=[];events=[]
        async def query(messages):sent.append(messages);return 'ok'
        guard=p.FirstRequestGuard(p.digest(messages),events.append)
        call=guard.wrap(query)
        self.assertEqual(asyncio.run(call(messages)),'ok')
        asyncio.run(call([dict(role='user',content='new legitimate search feedback')]))
        self.assertEqual(len(sent),2);self.assertEqual(len(events),1)

    def test_public_manifest_does_not_read_siblings(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pub=root/'public';pub.mkdir();(pub/'train.txt').write_text('public')
            (root/'private-reference').mkdir();(root/'private-reference'/'labels.txt').write_text('must not enter')
            rows=p.public_manifest(pub)
            self.assertEqual([r['path'] for r in rows],['train.txt'])

    def test_hook_overrides_only_preview_not_cleanup(self):
        sent=[];events=[];messages=[dict(role='user',content='same public input')]
        class Solver:
            def update_data_preview(self,state):raise AssertionError('must not start preview kernel')
        class Client:
            async def query(self,messages):sent.append(messages);return 'ok'
        class LLM:
            def __init__(self):self.client=Client()
        p.install(Solver,LLM,'data/\n  train/',p.digest(messages),events.append)
        solver=Solver();solver.update_data_preview({})
        self.assertEqual(solver.data_preview,'data/\n  train/')
        self.assertEqual(asyncio.run(LLM().client.query(messages)),'ok')
        self.assertEqual(len(sent),1)
        self.assertEqual([e['event'] for e in events],['fixed_public_preview_loaded','first_request_input_gate'])


if __name__=='__main__':unittest.main()
