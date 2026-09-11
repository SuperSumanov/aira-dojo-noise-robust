import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import forets_paid_budget_20260911 as b
import forets_paid_transport_20260911 as t


class PaidBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'ledger.sqlite'
        b.initialize(self.path, [str(x) for x in range(8)])

    def test_unknown_cannot_refund_and_equal_scope_cap(self):
        b.reserve(self.path,'0','a')
        with self.assertRaises(b.BudgetStopped): b.reserve(self.path,'0','b')
        self.assertEqual(b.snapshot(self.path)['accounted_usd'],0.7)
        b.settle(self.path,'a',{'cost':0.0000123456})
        b.reserve(self.path,'0','b')
        self.assertEqual(b.snapshot(self.path)['unresolved'],1)

    def test_bad_cost_stops(self):
        for invalid in (None,-1,float('nan'),float('inf'),True,'no'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as d:
                p=Path(d)/'l'; b.initialize(p,[str(x) for x in range(8)]); b.reserve(p,'0','x')
                with self.assertRaises(b.BudgetStopped): b.settle(p,'x',{'cost':invalid})
                self.assertEqual(b.snapshot(p)['accounted_usd'],0.7)
                with self.assertRaises(b.BudgetStopped): b.reserve(p,'1','y')

    def test_duplicate_and_overrun(self):
        b.reserve(self.path,'0','a')
        with self.assertRaises(Exception): b.reserve(self.path,'1','a')
        with self.assertRaises(b.BudgetStopped): b.settle(self.path,'a',{'cost':0.71})
        self.assertEqual(b.snapshot(self.path)['settled_usd'],0.71)
        with self.assertRaises(b.BudgetStopped): b.reserve(self.path,'1','b')

    def test_atomic_concurrency(self):
        def attempt(i):
            try: b.reserve(self.path,'0',str(i)); return 1
            except b.BudgetStopped: return 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt,range(16))),1)

    def test_no_reinitialize(self):
        with self.assertRaises(FileExistsError): b.initialize(self.path,[str(x) for x in range(8)])

    def test_payload_blocks_billing_extras_and_fallback(self):
        k=dict(model='openai/'+b.MODEL,base_url='https://openrouter.ai/api/v1',
               extra_body={'provider':b.PROVIDER},max_tokens=8192,temperature=.6,top_p=.95)
        m=[dict(role='user',content='public fixture')]
        self.assertEqual(t.payload_for(m,k)['model'],b.MODEL)
        for more in ({'plugins':[]},{'max_tokens':9000},{'extra_body':{}},{'model':'other'}):
            with self.assertRaises(b.BudgetStopped): t.payload_for(m,k|more)
        with self.assertRaises(b.BudgetStopped): t.payload_for([dict(role='user',content=[])],k)

    def test_worst_full_context_and_fee_margin(self):
        self.assertGreaterEqual(b.RESERVE/b.UNIT,1000000*.65/1e6+8192*2.6/1e6)
        self.assertLessEqual(10*8*1.1,100)
        self.assertEqual(8*b.AUTH['run_limit']+b.AUTH['route_limit'],b.AUTH['total'])


if __name__=='__main__': unittest.main()
