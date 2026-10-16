import ast
from pathlib import Path
import unittest
from colocation_pool_20261016 import State,audit
from colocation_readout_20261016 import quality,verify_queue,TASKS,ORDER
from colocation_coexistence_20261016 import validate

class Tests(unittest.TestCase):
    def test_shared_four_max(self):
        s=State("shared")
        for i in range(9):s.request(str(i),i%4)
        self.assertEqual([s.admit(str(i)) for i in range(4)],list(range(4)))
        self.assertIsNone(s.admit("4"))
    def test_colocated_uses_empty_before_sharing(self):
        s=State("colocated")
        for i in range(9):s.request(str(i),i%4)
        self.assertEqual([s.admit(str(i)) for i in range(8)],list(range(4))*2)
        self.assertIsNone(s.admit("8"))
        s.release("2",True);self.assertEqual(s.admit("8"),2)
    def test_fifo(self):
        s=State("colocated");s.request("a",0);s.request("b",1)
        self.assertIsNone(s.admit("b"))
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            State("colocated",active={"a":dict(device=0),"b":dict(device=0),"c":dict(device=0)})
        with self.assertRaises(ValueError):
            State("shared",active={"a":dict(device=0),"b":dict(device=0)})
        State("colocated",active={"a":dict(device=0),"b":dict(device=0)})
    def test_no_unsafe_release(self):
        s=State("colocated");s.request("a",0);s.admit("a")
        with self.assertRaises(ValueError):s.release("a",False)
        with self.assertRaises(ValueError):s.cancel("a")
    def test_cancel_never_reuse(self):
        s=State("colocated");s.request("a",0);s.cancel("a")
        with self.assertRaises(ValueError):s.request("a",0)
    def test_full_replay(self):
        state=State("colocated");events=[];t=0
        def emit(event,key,device=None):
            nonlocal t
            t+=1;events.append(dict(event=event,key=key,device=device,home=int(key)%4,
                time=t,active=len(state.active),queued=len(state.queue)))
        for i in range(8):
            k=str(i);state.request(k,i%4);emit("queued",k)
            d=state.admit(k);emit("admitted",k,d)
        for i in range(8):
            state.release(str(i),True);emit("released",str(i),i%4)
        self.assertTrue(audit(events,"colocated")["all_released"])
        r=verify_queue(events,"colocated")
        self.assertEqual(r["co_admissions"],4);self.assertEqual(r["peak_device_leases"],2)
        with self.assertRaises(AssertionError):verify_queue(events,"shared")
    def fixture(self):
        return [dict(block=b,task=t,score=(.99 if k==0 else .02-(.002 if ORDER[b]=="colocated" else 0)))
                for b in range(4) for k,t in enumerate(TASKS) for _ in range(4)]
    def test_quality_and_full_denominator(self):
        self.assertTrue(quality(self.fixture())[2])
        with self.assertRaises(AssertionError):quality(self.fixture()[:-1])
    def test_no_pooled_rescue(self):
        rows=self.fixture()
        for r in rows:
            if r["block"]==2 and r["task"]==TASKS[1]:r["score"]=.0201
        self.assertFalse(quality(rows)[2])
    def test_no_aerial_rescue(self):
        rows=self.fixture()
        for r in rows:
            if r["block"]==1 and r["task"]==TASKS[0]:r["score"]=.98
        self.assertFalse(quality(rows)[2])
    def test_cpu_partition_unchanged(self):
        tree=ast.parse(Path(__file__).with_name("colocation_trial_20261016.py").read_text())
        f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="cpu_slots")
        ns={};exec(compile(ast.Module(body=[f],type_ignores=[]),"<cpu partition>","exec"),ns)
        self.assertEqual(ns["cpu_slots"]([dict(logical_cpu=i,socket=0,core=i%16) for i in range(32)]),
                         [[2*i,2*i+1] for i in range(8)])
    def test_coexistence_receipt(self):
        rows=[dict(slot=i,passed=True,devices=1,result=16777216,held_bytes=134217728,both_ready=True,both_done=True) for i in (0,1)]
        validate(rows)
        rows[1]["both_done"]=False
        with self.assertRaises(AssertionError):validate(rows)

if __name__=="__main__":unittest.main()
