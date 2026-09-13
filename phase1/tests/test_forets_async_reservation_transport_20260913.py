"""Actual future transport, with only wire/account boundaries mocked."""
import asyncio
import os
import sys
from unittest.mock import patch
from test_forets_parallel_20260912 import TransportTests
from build_forets_branching_20260913 import changed_sources, PREFIX


class AsyncTransportTests(TransportTests):
    def setUp(self):
        super().setUp()
        self.source=changed_sources()[PREFIX+'paid_transport.py'].decode()
        sync=self.budget.reserve
        async def reserve(*args):
            await asyncio.sleep(.001)
            sync(*args)
        self.budget.reserve_async=reserve

    async def test_wire_payload_and_bounded_actual_concurrency(self):
        with patch.dict(sys.modules,self.modules),patch.dict(os.environ,FORETS_PAID_LEDGER='/synthetic',FORETS_PAID_SCOPE='synthetic'):
            new=self.module(self.source)
            responses=await asyncio.gather(*(new.complete(self.messages,self.kwargs,120,str(i)) for i in range(9)))
            self.assertEqual(self.peak,4);self.assertEqual(len(self.posts),9)
            self.assertEqual(list(self.reserved.values()),['settled']*9)
            self.assertTrue(all(r.usage['cost']==.01 for r in responses))

    async def test_cancel_keeps_reservation_and_no_retry(self):
        self.block=True
        with patch.dict(sys.modules,self.modules),patch.dict(os.environ,FORETS_PAID_LEDGER='/synthetic',FORETS_PAID_SCOPE='synthetic'):
            new=self.module(self.source);task=asyncio.create_task(new.complete(self.messages,self.kwargs,120,'cancel'))
            await asyncio.wait_for(self.entered.wait(),1);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(self.reserved,{'cancel':'unresolved'});self.assertEqual(len(self.posts),1)

    async def test_no_wire_before_reservation(self):
        self.reject=True
        with patch.dict(sys.modules,self.modules),patch.dict(os.environ,FORETS_PAID_LEDGER='/synthetic',FORETS_PAID_SCOPE='synthetic'):
            new=self.module(self.source)
            with self.assertRaises(RuntimeError):await new.complete(self.messages,self.kwargs,120,'reject')
            self.assertFalse(self.posts);self.assertFalse(self.reserved)

    def test_repeated_patch_is_rejected(self):
        self.assertIn('await reserve_async(path, scope, attempt_id)',self.source)
        rank=changed_sources()['src/dojo/solvers/fore_ts/contextual_rank.py'].decode()
        self.assertIn('await paid_budget.reserve_async(',rank)


if __name__=='__main__':
    import unittest
    unittest.main()
