import sqlite3
import tempfile
from pathlib import Path
import sys
import unittest
from contextlib import closing
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forets_reserve_backpressure_20260913 import reserve_wait, patch_budget


class Stopped(RuntimeError): pass


class ReserveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'ledger.sqlite'
        self.now = 1000.
        self.auth = dict(total=2100000000)
        self.state = 'active'
        self.admissions = 0
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript('CREATE TABLE scopes(scope TEXT PRIMARY KEY,cap INTEGER);'
                'CREATE TABLE calls(id TEXT PRIMARY KEY,scope TEXT,held INTEGER,cost INTEGER,state TEXT,created REAL);')
            db.executemany('INSERT INTO scopes VALUES (?,?)',[('a',2100000000),('b',2100000000)])

    def tearDown(self): self.tmp.cleanup()
    def connect(self, path):
        if self.state != 'active': raise Stopped(self.state)
        db=sqlite3.connect(path, timeout=.2);db.execute('BEGIN IMMEDIATE');return db
    def authorize(self):
        self.admissions += 1
        if self.now >= 1001: raise TimeoutError('deadline')
    def sleep(self, seconds): self.now += seconds
    def add(self, ident, scope, held, state='unresolved', age=0):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?)',(ident,scope,held,None,state,self.now-age))
    def call(self, **kw):
        args=dict(connect=self.connect,authorize=self.authorize,auth=self.auth,stopped_error=Stopped,
            clock=lambda:self.now,wall=lambda:self.now,sleep=self.sleep,max_wait=.5,poll=.1)
        args.update(kw)
        reserve_wait(self.path,'a','new',700000000,**args)
    def test_immediate(self):
        self.call();self.assertEqual(self.admissions,2)
    def test_settlement_can_lock_while_waiting(self):
        self.add('old','b',1400000000,age=10000);self.add('flight','b',700000000)
        def settle(dt):
            self.sleep(dt)
            with closing(sqlite3.connect(self.path,timeout=.2)) as db, db:
                db.execute("UPDATE calls SET held=1000,cost=1000,state='settled' WHERE id='flight'")
        self.auth['total'] += 1000
        self.call(sleep=settle)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertLessEqual(db.execute('SELECT sum(held) FROM calls').fetchone()[0], self.auth['total'])
            self.assertEqual(db.execute("SELECT held,state FROM calls WHERE id='old'").fetchone(),(1400000000,'unresolved'))
    def test_old_unknown_never_freed(self):
        self.add('old','b',2100000000,age=10000)
        with self.assertRaises(Stopped): self.call()
        self.assertEqual(self.now,1000.)
    def test_permanent_scope_failure(self):
        self.add('settled','a',2100000000,'settled')
        self.add('flight','b',700000000)
        with self.assertRaises(Stopped): self.call()
        self.assertEqual(self.now,1000.)
    def test_wait_bounded_and_no_insert(self):
        self.add('flight','b',2100000000)
        with self.assertRaises(Stopped): self.call()
        self.assertAlmostEqual(self.now,1000.5)
        with closing(sqlite3.connect(self.path)) as db: self.assertEqual(db.execute('SELECT count(*) FROM calls').fetchone()[0],1)
    def test_deadline_during_wait(self):
        self.add('flight','b',2100000000)
        with self.assertRaises(TimeoutError): self.call(max_wait=5)
    def test_auth_stopped_while_waiting(self):
        self.add('flight','b',2100000000)
        def halt(dt):self.sleep(dt);self.state='stopped'
        with self.assertRaisesRegex(Stopped,'stopped'): self.call(sleep=halt)
    def test_limit(self):
        for i in range(100):self.add(str(i),'a',1,'settled')
        with self.assertRaises(Stopped):self.call()
    def test_patch_actual_source(self):
        import subprocess
        raw=subprocess.check_output(['git','show','1ec18564f176d58a3a7ac3a46852ad92044777b5:src/dojo/core/solvers/llm_helpers/backends/paid_budget.py']).decode()
        patched=patch_budget(raw);compile(patched,'actual-budget','exec')
        self.assertEqual(raw[raw.index('def settle('):],patched[patched.index('def settle('):])


if __name__=='__main__':unittest.main()
