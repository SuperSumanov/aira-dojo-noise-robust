import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import owned_cgroup_pressure as c


class Tests(unittest.TestCase):
    def test_target_leaf_not_observer_leaf_and_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);leaf=root/'worker';leaf.mkdir()
            (leaf/'pids.current').write_text('7')
            (leaf/'pids.max').write_text('12')
            (root/'pids.current').write_text('31')
            out=c.counters('0::/worker\n',root)
            self.assertEqual(out['ancestors'][0]['counters']['pids.current'],7)
            self.assertEqual(out['ancestors'][1]['counters']['pids.current'],31)
            self.assertIsNone(out['ancestors'][0]['counters']['memory.current'])
            self.assertNotIn('worker',json.dumps(out))

    def test_namespace_escape_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=c.counters('0::/../../worker\n',Path(tmp))
            self.assertEqual(out['ancestors'],[])
            self.assertEqual(out['unsupported_or_truncated'],1)

    def test_deduplicate_only_after_identity_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp)/'proc';proc.mkdir();root=Path(tmp)/'cgroups';root.mkdir()
            for pid in (10,11):
                (proc/str(pid)).mkdir();(proc/str(pid)/'cgroup').write_text('0::/\n')
            def identity(directory,uid):
                return dict(pid=int(directory.name),start_ticks=2,uid=uid)
            records=[dict(pid=10,start_ticks=2),dict(pid=11,start_ticks=2)]
            with patch.object(c.process,'process_record',side_effect=identity):
                out=c.collect(records,proc,root)
            self.assertEqual(len(out['groups']),1)
            self.assertEqual(out['groups'][0]['members'],[10,11])
            self.assertEqual(out['skipped_or_racing_pids'],[])

    def test_pid_reuse_skipped_before_group_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(c.process,'process_record',return_value=dict(pid=10,start_ticks=99)):
                out=c.collect([dict(pid=10,start_ticks=2)],Path(tmp),Path(tmp))
            self.assertEqual(out['groups'],[])
            self.assertEqual(out['skipped_or_racing_pids'],[10])


if __name__=='__main__':unittest.main()
