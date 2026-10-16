import unittest
import importlib.util
from unittest.mock import patch
import clock_pairing_20261017 as current


class WindowTests(unittest.TestCase):
    def test_frozen_design_unchanged(self):
        before=current.frozen.schedule();groups=[current.frozen.groups(b) for b in range(4)]
        current.configure()
        self.assertEqual(before,current.frozen.schedule())
        self.assertEqual(groups,[current.frozen.groups(b) for b in range(4)])
        self.assertEqual(current.frozen.CAP,3120)
        self.assertNotEqual(current.ROOT,current.frozen.OLD)
    def test_fresh_guard(self):
        current.guard_after_hash(current.WINDOW_END-3300)
        with self.assertRaises(RuntimeError):current.guard_after_hash(current.WINDOW_END-3299)
    def test_second_import_after_configure(self):
        current.configure()
        spec=importlib.util.spec_from_file_location('second_pairing_import',current.__file__)
        second=importlib.util.module_from_spec(spec);spec.loader.exec_module(second)
        second.configure()
        self.assertIs(second.ORIGINAL_PREPARE,current.ORIGINAL_PREPARE)
        self.assertEqual(second.frozen.schedule(),current.frozen.schedule())
    def test_guard_after_hash_before_intent(self):
        current.configure();events=[];b=current.frozen.base
        with patch.object(b,'check',return_value=dict(task_image='/not-real',task_image_sha256='x')), \
             patch.object(b,'sha',side_effect=lambda p:events.append('hash') or 'x'), \
             patch.object(current.time,'time',return_value=current.WINDOW_END-1), \
             patch.object(b,'write') as write,patch.object(current.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):current.submit()
            self.assertEqual(events,['hash']);write.assert_not_called();run.assert_not_called()


if __name__=='__main__':unittest.main()
