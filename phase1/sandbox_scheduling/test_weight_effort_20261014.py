import asyncio
import contextvars
from pathlib import Path
from types import SimpleNamespace
import unittest
import weight_effort_policy_20261014 as p
from weight_effort_readout_20261014 import quality, TASKS


class Tests(unittest.TestCase):
    def fixture(self, arm, role):
        return SimpleNamespace(client=SimpleNamespace(model='openai/'+p.model(arm)), generation_kwargs=dict(
            reasoning_effort=p.effort(arm, role), max_tokens=8192 if role == 'analyze' else 32768,
            bounded_request_timeout_seconds=600 if role == 'analyze' else 1500,
            extra_body=dict(chat_template_kwargs=dict(enable_thinking=p.effort(arm, role) != 'none'))))

    def test_matrix_budget(self):
        self.assertEqual(set(p.ORDER), set(p.ARMS))
        self.assertEqual(len(p.ORDER)*8, 32)
        self.assertEqual(p.CAP*6/3600, 15)
        self.assertLess(4*p.SLOT+600+180+90, p.CAP)
        for arm in p.ARMS:
            self.assertEqual(p.effort(arm, 'analyze'), 'medium')
            self.assertEqual(p.effort(arm, 'improve'), 'none' if arm.endswith('fast') else 'medium')

    def test_normalization_only_two_factors(self):
        def cfg(arm): return dict(solver=dict(operators={r: dict(llm=dict(client=dict(model_id=p.model(arm), base_url='local'), generation_kwargs=self.fixture(arm, r).generation_kwargs)) for r in p.ROLES}))
        a, b = cfg('old_fast'), cfg('new_medium')
        self.assertEqual(p.normalize(a), p.normalize(b))
        b['solver']['operators']['improve']['llm']['client']['base_url'] = 'changed'
        self.assertNotEqual(p.normalize(a), p.normalize(b))

    def test_trace_and_misrouting(self):
        p.old.effort = p.effort
        for arm in p.ARMS:
            for role in p.ROLES:
                events = []
                async def native(self): return 'fixture', dict(usage=dict(completion_tokens=2, finish_reason='stop'), prompt_messages=[dict(role='user', content='same')])
                wrap = p.trace(native, dict(arm=arm), Path('.'), SimpleNamespace(elapsed=lambda: 0),
                    contextvars.ContextVar('role', default=role), lambda path, event: events.append(event))
                llm = self.fixture(arm, role)
                asyncio.run(wrap(llm))
                self.assertEqual(events[-1]['model_id'], p.model(arm))
                self.assertTrue(events[-1]['success'])
                llm.client.model = 'wrong-model'
                with self.assertRaises(AssertionError): asyncio.run(wrap(llm))

    def test_primary_not_rescued_by_fast(self):
        scores = {(a, t): .999 if t == TASKS[0] else .02 for a in p.ARMS for t in TASKS}
        scores['new_fast', TASKS[1]] = .001
        self.assertFalse(quality(scores)[1])
        scores['new_medium', TASKS[1]] = .018
        self.assertTrue(quality(scores)[1])
        scores['new_medium', TASKS[0]] = .998
        self.assertFalse(quality(scores)[1])


if __name__ == '__main__': unittest.main()
