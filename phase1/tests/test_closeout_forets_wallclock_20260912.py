import hashlib
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import closeout_forets_wallclock_20260912 as target


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        self.quiet=redirect_stdout(io.StringIO());self.quiet.__enter__();self.addCleanup(self.quiet.__exit__,None,None,None)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.code=self.root/'code';self.code.mkdir()
        files={}
        for name in ('closeout_forets_wallclock_20260912.py','readout_forets_wallclock_20260912.py','readout_forets_generation_capacity_20260912.py'):
            (self.code/name).write_text('pass\n');files[name]=hashlib.sha256((self.code/name).read_bytes()).hexdigest()
        (self.root/'closeout-intent.json').write_text(json.dumps(dict(directory=str(self.code),files=files,maximum_wait_seconds=10,maximum_readout_seconds=1)))
        self.binding=patch.object(target,'bound',return_value=(self.root,{'job':'13152'}));self.binding.start();self.addCleanup(self.binding.stop)
    def finish(self):return json.loads((self.root/'closeout-finished.json').read_text())
    def test_waits_for_terminal_then_exactly_one_reader(self):
        def reader(*a,**k):
            (self.root/'wallclock-summary.json').write_text('{}');(self.root/'wallclock-runs.csv').write_text('header\n')
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        with (patch.object(target.subprocess,'check_output',side_effect=['13152|RUNNING|gpu28|5','13152|COMPLETED|gpu28|7']),
              patch.object(target.time,'sleep') as sleep,patch.object(target.subprocess,'run',side_effect=reader) as run):
            target.run(self.root)
            self.assertEqual(sleep.call_count,1);self.assertEqual(run.call_count,1)
        self.assertEqual(self.finish()['status'],'verified')
    def test_hash_drift_never_reads_effects(self):
        (self.code/'readout_forets_wallclock_20260912.py').write_text('changed\n')
        with patch.object(target.subprocess,'check_output',return_value='13152|COMPLETED|gpu28|7'),patch.object(target.subprocess,'run') as run:
            target.run(self.root);run.assert_not_called()
        self.assertFalse(self.finish()['readout_called'])
    def test_ambiguous_state_no_reader_or_silent_retry(self):
        with (patch.object(target.subprocess,'check_output',return_value='13152|RUNNING|gpu28|5\n13152|COMPLETED|gpu28|7') as query,
              patch.object(target.subprocess,'run') as run):
            target.run(self.root);run.assert_not_called();self.assertEqual(query.call_count,1)
        self.assertFalse(self.finish()['readout_called'])
    def test_explicit_successor_seeds_reach_reader(self):
        path=self.root/'closeout-intent.json'
        intent=json.loads(path.read_text());intent['seeds']=[24,25];path.write_text(json.dumps(intent))
        def reader(command,**kwargs):
            self.assertEqual(command[-3:],['--seeds','24','25'])
            (self.root/'wallclock-summary.json').write_text('{}');(self.root/'wallclock-runs.csv').write_text('header\n')
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        with patch.object(target.subprocess,'check_output',return_value='13152|COMPLETED|gpu28|7'),patch.object(target.subprocess,'run',side_effect=reader):
            target.run(self.root,seeds=(24,25))
        self.assertEqual(self.finish()['status'],'verified')


if __name__=='__main__':unittest.main()
