"""CPU-only migration contract, without importing mutable wrapper globals."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class PlacementTests(unittest.TestCase):
    def test_gpu27_migration_keeps_frozen_science(self):
        command = '''import json
import live_gpu27_trial as entry
t=entry.trial
print(json.dumps(dict(root=str(t.R),node=t.NODE,name=t.NAME,
    qualification=t.NODE_QUALIFICATION,profile=t.PROFILE,model=t.MODEL_ID,
    cap=t.CAP,files=t.FILES,rows=t.schedule())))
'''
        result = subprocess.run([sys.executable, '-B', '-c', command],
                                cwd=Path(__file__).parent, check=True,
                                capture_output=True, text=True)
        config = json.loads(result.stdout)
        self.assertTrue(config['root'].endswith('scheduling-live-search-20261009-v4'))
        self.assertEqual(config['node'], 'gpu27')
        self.assertEqual(config['name'], 'live_gpu27_trial.py')
        self.assertTrue(config['qualification'])
        self.assertEqual(config['profile'], '27b')
        self.assertEqual(config['model'], 'qwen3.8-27b')
        self.assertEqual(config['cap'], 5400)
        self.assertIn('live_node_qualification.py', config['files'])
        from live_search_trial_20261009 import schedule
        self.assertEqual(config['rows'], schedule())
        self.assertEqual(len(config['files']), len(set(config['files'])))


if __name__ == '__main__':
    unittest.main()
