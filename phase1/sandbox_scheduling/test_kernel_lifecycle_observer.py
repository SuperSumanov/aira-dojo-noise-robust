import asyncio,types,unittest
from kernel_lifecycle_observer import wrap

class Tests(unittest.TestCase):
    def make(self):
        class Fake:
            process=None
            async def launch_kernel(self,*args,**kwargs):
                self.process=types.SimpleNamespace(pid=7);return {'unchanged':'result'}
            async def poll(self):return self.returncode
        return Fake
    def test_exact_return_and_deduplicated_exit(self):
        cls=self.make();events=[];wrap(cls,events.append);obj=cls()
        self.assertEqual(asyncio.run(obj.launch_kernel('untouched')),{'unchanged':'result'})
        obj.returncode=None;self.assertIsNone(asyncio.run(obj.poll()))
        obj.returncode=-11
        self.assertEqual(asyncio.run(obj.poll()),-11);self.assertEqual(asyncio.run(obj.poll()),-11)
        self.assertEqual([x['event'] for x in events],['launched','exit_observed'])
        self.assertEqual(events[-1]['returncode'],-11)
    def test_observer_failure_does_not_change_kernel(self):
        cls=self.make();wrap(cls,lambda _:(_ for _ in ()).throw(OSError()))
        obj=cls();asyncio.run(obj.launch_kernel());obj.returncode=0
        self.assertEqual(asyncio.run(obj.poll()),0)
    def test_original_error_preserved(self):
        cls=self.make()
        async def bad(self):raise ValueError('original')
        cls.poll=bad;events=[];wrap(cls,events.append)
        with self.assertRaisesRegex(ValueError,'original'):asyncio.run(cls().poll())
        self.assertEqual(events,[])

if __name__=='__main__':unittest.main()
