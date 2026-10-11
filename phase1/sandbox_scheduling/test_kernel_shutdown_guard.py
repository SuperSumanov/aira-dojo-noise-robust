import asyncio,types,unittest
from kernel_shutdown_guard import wait_ready_transition,overlay_method

class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_is_unchanged(self):
        f=asyncio.get_running_loop().create_future();f.set_result(19)
        await wait_ready_transition(types.SimpleNamespace(ready=f))
        self.assertEqual(f.result(),19)
    async def test_pending_waits_then_preserves_result(self):
        f=asyncio.get_running_loop().create_future();km=types.SimpleNamespace(ready=f)
        task=asyncio.create_task(wait_ready_transition(km));await asyncio.sleep(0)
        self.assertFalse(task.done());f.set_result(None);await task
        self.assertFalse(f.cancelled())
    async def test_pending_failure_left_for_original_handler(self):
        f=asyncio.get_running_loop().create_future();km=types.SimpleNamespace(ready=f)
        task=asyncio.create_task(wait_ready_transition(km));await asyncio.sleep(0)
        exc=ValueError('original');f.set_exception(exc);await task
        self.assertIs(f.exception(),exc)
    async def test_timeout_does_not_cancel_lifecycle(self):
        f=asyncio.get_running_loop().create_future()
        with self.assertRaises(TimeoutError):await wait_ready_transition(types.SimpleNamespace(ready=f),0.01)
        self.assertFalse(f.done());f.set_result(None)
    async def test_caller_cancel_does_not_cancel_lifecycle(self):
        f=asyncio.get_running_loop().create_future()
        task=asyncio.create_task(wait_ready_transition(types.SimpleNamespace(ready=f)))
        await asyncio.sleep(0);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(f.done());f.set_result(None)
    async def test_second_transition_also_waited(self):
        loop=asyncio.get_running_loop();f=loop.create_future();g=loop.create_future();km=types.SimpleNamespace(ready=f)
        task=asyncio.create_task(wait_ready_transition(km));await asyncio.sleep(0)
        km.ready=g;f.set_result(None);await asyncio.sleep(0);await asyncio.sleep(0)
        self.assertFalse(task.done());g.set_result(None);await task
    async def test_cancelled_ready_preserved(self):
        f=asyncio.get_running_loop().create_future();f.cancel()
        await wait_ready_transition(types.SimpleNamespace(ready=f));self.assertTrue(f.cancelled())
    def test_overlay_is_only_insertion_and_rejects_drift(self):
        text='    async def _async_shutdown_kernel(self):\n        km=self.get_kernel()\n        # If a pending kernel raised an exception, remove it.\n        return km.ready.exception()\n'
        result=overlay_method(text)
        self.assertIn('await _r14_wait_ready_transition(km)',result)
        with self.assertRaises(ValueError):overlay_method(text.replace('pending kernel','unknown'))
        with self.assertRaises(ValueError):overlay_method(text+text)

if __name__=='__main__':unittest.main()
