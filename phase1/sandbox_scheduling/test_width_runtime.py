import concurrent.futures as cf
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import neural_width_trial as trial
from lifecycle_pilot import read,write
from width_readout import peak


class WidthRuntimeTests(unittest.TestCase):
    def test_batch_declares_same_physical_resources_and_no_conflicting_bind(self):
        text=trial.batch_script()
        self.assertIn('--gres=gpu:1',text);self.assertIn('--cpus-per-task=6',text)
        self.assertIn('--hint=nomultithread',text);self.assertNotIn('--cpu-bind',text)
        self.assertIn('--time=01:30:00',text)

    def test_generated_shim_target_exists(self):
        # Exact import target used by prepare, without loading any GPU runtime.
        scope={};exec('from neural_width_trial import configure',scope)
        self.assertIs(scope['configure'],trial.configure)

    @unittest.skipUnless(os.name=='posix','native flock contract exercised on remote Linux')
    def test_real_file_barrier_all_widths(self):
        for block,width in ((0,1),(1,2),(2,4)):
            with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp,patch.object(trial,'R',Path(tmp)):
                root=Path(tmp);(root/f'mutex-{block}').touch()
                for i in range(4*block,4*block+4):(root/f'episode-{i}').mkdir()
                def run(index):
                    ep=root/f'episode-{index}'
                    trial.boundary_write(ep/'candidate_started.json',dict(time=time.time()))
                    time.sleep(.05 if index%2 else .12)
                    write(ep/'completed.json',dict(complete=True))
                    trial.boundary_write(ep/'closed.json',dict(returncode=0,end=time.time()))
                with cf.ThreadPoolExecutor(max_workers=4) as pool:
                    fs=[pool.submit(run,i) for i in reversed(range(4*block,4*block+4))]
                    for future in fs:future.result(timeout=5)
                spans=[(read(root/f'episode-{i}/execution_admitted.json')['time'],read(root/f'episode-{i}/closed.json')['end'])
                       for i in range(4*block,4*block+4)]
                self.assertLessEqual(peak(spans),width)
                self.assertEqual([a for a,b in spans],sorted(a for a,b in spans))


if __name__=='__main__':unittest.main()
