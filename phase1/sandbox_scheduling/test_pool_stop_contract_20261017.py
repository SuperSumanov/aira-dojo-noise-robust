import json
from pathlib import Path
import tempfile
import unittest
from pool_stop_contract_20261017 import require_completed_workers


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='pool-stop-test-',dir=Path.cwd());self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.rows=[dict(index=i) for i in range(8)]
        self.results=[dict(index=i,returncode=0,cleanup_verified=True,finished=True) for i in range(8)]
        for r in self.rows:
            p=self.root/f"episode-{r['index']}";p.mkdir();(p/'finished.json').write_text(json.dumps(dict(status='budget_exhausted')))
    def test_normal_budget_end(self):self.assertTrue(require_completed_workers(self.root,self.rows,self.results))
    def test_candidate_failure_does_not_become_infrastructure_failure(self):
        (self.root/'episode-0/finished.json').write_text(json.dumps(dict(status='completed',valid=False)))
        self.assertTrue(require_completed_workers(self.root,self.rows,self.results))
    def test_worker_nonzero_even_if_cleanup_succeeded(self):
        self.results[0]['returncode']=1
        with self.assertRaises(RuntimeError):require_completed_workers(self.root,self.rows,self.results)
    def test_missing_worker(self):
        with self.assertRaises(RuntimeError):require_completed_workers(self.root,self.rows,self.results[:-1])
    def test_missing_completion(self):
        self.results[0]['finished']=False
        with self.assertRaises(RuntimeError):require_completed_workers(self.root,self.rows,self.results)
    def test_bad_worker_status(self):
        (self.root/'episode-0/finished.json').write_text(json.dumps(dict(status='failed')))
        with self.assertRaises(RuntimeError):require_completed_workers(self.root,self.rows,self.results)
    def test_failed_cleanup(self):
        self.results[0]['cleanup_verified']=False
        with self.assertRaises(RuntimeError):require_completed_workers(self.root,self.rows,self.results)


if __name__=='__main__':unittest.main()
