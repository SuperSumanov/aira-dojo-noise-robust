import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

class CapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('asset_test',Path(__file__).with_name('prepare_local_generator_assets_20260914.py'))
        cls.module=importlib.util.module_from_spec(spec)
        # Only the pure capacity calculation is tested here, not flock/fallocate.
        with patch.dict(sys.modules,{'fcntl':types.ModuleType('fcntl')}):
            spec.loader.exec_module(cls.module)

    def test_completed_image_is_not_reserved_twice(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'image').write_bytes(b'0123456789')
            entries=[{'path':'image','size':10},{'path':'weight','size':40}]
            self.assertEqual(self.module.capacity_required(root,entries),2*1024**3+40)

    def test_wrong_existing_size_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'image').write_bytes(b'bad')
            with self.assertRaises(ValueError):self.module.capacity_required(root,[{'path':'image','size':10}])

    def test_partial_object_still_reserves_conservatively(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'image.partial').write_bytes(b'123')
            self.assertEqual(self.module.capacity_required(root,[{'path':'image','size':10}]),2*1024**3+10)

if __name__=='__main__':unittest.main()
