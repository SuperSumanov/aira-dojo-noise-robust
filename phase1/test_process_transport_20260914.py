import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
import diagnose_process_transport_20260914 as d


class Transport(unittest.TestCase):
    def test_payload_replacement_keeps_full_prefix(self):
        prefix=['runtime','exec','--containall','--cleanenv','--no-home','--nv','--bind','a:b:ro',
                '--pwd','/workspace','image.sif','env','HOME=/workspace/.home','CUDA_VISIBLE_DEVICES=4']
        args=prefix+['python','-c','original bootstrap','kernelgateway','--auth','test-only']
        self.assertEqual(d.replace_bootstrap(args,'image.sif','print(1)'),prefix+['python','-c','print(1)'])
        self.assertEqual(args[-1],'test-only')

    def test_reject_different_bootstrap_and_ambiguous_image(self):
        for args in (['image','python','-m','jupyter'],['image','image','python','-c','x']):
            with self.assertRaises(ValueError):d.replace_bootstrap(args,'image','x')

    def test_stopped_child_never_signalled(self):
        child=Mock();child.poll.return_value=0
        with patch.object(d.os,'killpg',create=True) as kill:
            d.stop_owned(child);kill.assert_not_called()

    def test_non_owned_group_never_signalled(self):
        child=Mock(pid=12345);child.poll.return_value=None
        with patch.object(d.os,'getpgid',return_value=54321,create=True),patch.object(d.os,'killpg',create=True) as kill:
            with self.assertRaises(ValueError):d.stop_owned(child)
            kill.assert_not_called()

    def test_exclusive_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'receipt.json';d.write(p,{'api_calls':0})
            with self.assertRaises(FileExistsError):d.write(p,{'api_calls':1})
            self.assertEqual(d.read(p),{'api_calls':0})


if __name__=='__main__':unittest.main()
