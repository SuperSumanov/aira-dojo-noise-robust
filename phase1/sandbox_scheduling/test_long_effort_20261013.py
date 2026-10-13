import asyncio
import contextvars
from pathlib import Path
from types import SimpleNamespace
import unittest
from long_effort_policy_20261013 import ARMS, ROLES, ORDER, RUN, SLOT, CAP, effort, normalize, traced_call
from long_effort_readout_20261013 import quality, TASKS

class Tests(unittest.TestCase):
    def fixture(self, arm, role):
        e = effort(arm, role)
        return SimpleNamespace(generation_kwargs=dict(seed=9, reasoning_effort=e,
            max_tokens=8192 if role == 'analyze' else 32768,
            bounded_request_timeout_seconds=600 if role == 'analyze' else 1500,
            extra_body={'chat_template_kwargs': {'enable_thinking': e != 'none'}}))
    def test_exact_modes(self):
        self.assertEqual([[effort(a, r) for r in ROLES] for a in ARMS],
            [['none', 'none', 'none', 'medium'], ['medium']*4, ['xhigh', 'xhigh', 'xhigh', 'medium']])
        with self.assertRaises(ValueError): effort('feedback_think', 'improve')
        with self.assertRaises(ValueError): effort('xhigh', 'unknown')
    def test_budget_and_fixed_order(self):
        self.assertEqual(set(ORDER), set(ARMS))
        self.assertEqual(len(ORDER), 3)
        self.assertEqual(CAP*6/3600, 12.5)
        self.assertLess(3*SLOT+600+90, CAP)
        self.assertLess(RUN+90, SLOT-40)
    def test_config_normalization_preserves_other_knobs(self):
        def cfg(arm): return {'solver': {'operators': {r: {'llm': {'generation_kwargs': self.fixture(arm, r).generation_kwargs}} for r in ROLES}}}
        a, b = cfg('medium'), cfg('xhigh')
        self.assertEqual(normalize(a), normalize(b))
        b['solver']['operators']['improve']['llm']['generation_kwargs']['max_tokens'] = 8192
        self.assertNotEqual(normalize(a), normalize(b))
        self.assertEqual(a['solver']['operators']['improve']['llm']['generation_kwargs']['reasoning_effort'], 'medium')
    def test_all_modes_and_finish_reason(self):
        for arm in ARMS:
            for role in ROLES:
                events = []
                async def native(self): return 'private output', {'usage': {'completion_tokens': 4, 'finish_reason': 'length', 'private': 'do not export'}}
                wrapper = traced_call(native, dict(arm=arm), Path('.'), SimpleNamespace(elapsed=lambda: 1),
                    contextvars.ContextVar('role', default=role), lambda p, e: events.append(e))
                asyncio.run(wrapper(self.fixture(arm, role)))
                self.assertEqual(events[0]['usage'], {'completion_tokens': 4})
                self.assertEqual(events[0]['finish_reason'], 'length')
                self.assertTrue(events[0]['success'])
    def test_failure_propagated(self):
        events = []
        async def native(self): raise RuntimeError('fixture')
        wrapper = traced_call(native, dict(arm='xhigh'), Path('.'), SimpleNamespace(elapsed=lambda: 1),
            contextvars.ContextVar('role', default='improve'), lambda p, e: events.append(e))
        with self.assertRaises(RuntimeError): asyncio.run(wrapper(self.fixture('xhigh', 'improve')))
        self.assertFalse(events[0]['success'])
        self.assertIsNone(events[0]['finish_reason'])
    def test_quality_needs_both_references_and_no_aerial_regression(self):
        scores = {(a, t): (.999 if t == TASKS[0] else (.010 if a == 'xhigh' else .020)) for a in ARMS for t in TASKS}
        self.assertTrue(quality(scores)[1])
        scores['fast_code', TASKS[1]] = .009
        self.assertFalse(quality(scores)[1])
        scores['fast_code', TASKS[1]] = .020
        scores['xhigh', TASKS[0]] = .998
        self.assertFalse(quality(scores)[1])

if __name__ == '__main__': unittest.main()
