import ctypes
from pathlib import Path
import unittest
from unittest.mock import patch
import device_sweep_20261011 as d
from device_sweep_readout import summarize


class FakeCuda:
    def cuInit(self,flags):return 0
    def cuGetErrorName(self,rc,ptr):ptr._obj.value=b'CUDA_SUCCESS';return 0
    def cuDeviceGetCount(self,ptr):ptr._obj.value=8;return 0
    def cuDeviceGet(self,ptr,i):ptr._obj.value=i;return 0
    def cuDeviceGetUuid(self,ptr,dev):return 0


class DeviceSweepTests(unittest.TestCase):
    def test_only_standard_masks_exported(self):
        self.assertEqual(d.safe_mask('0,1'),'0,1')
        self.assertIsNone(d.safe_mask(None))
        self.assertEqual(d.safe_mask('not-a-device'),'<'+'nonstandard-suppressed>')

    def test_unset_options_and_bind_environment(self):
        cmd,env=d.image_command(Path('/tmp/slot'),'unset',dict(CUDA_VISIBLE_DEVICES='7',SINGULARITYENV_X='x',SINGULARITY_BIND='/data',PATH='/bin'))
        self.assertEqual(cmd[cmd.index('env')+1:cmd.index('env')+3],['-u','CUDA_VISIBLE_DEVICES'])
        self.assertEqual(env,{'PATH':'/bin'})
        default,env=d.image_command(Path('/tmp/slot'),'default',{'CUDA_VISIBLE_DEVICES':'7'})
        self.assertIn('CUDA_VISIBLE_DEVICES=7',default)
        self.assertNotIn('-u',default)

    def test_multivisible_never_imports_torch_or_computes(self):
        with patch.object(ctypes,'CDLL',return_value=FakeCuda()),patch.dict('sys.modules',{'torch':None}):
            result=d.probe(True)
        self.assertEqual(result['visible_devices'],8)
        self.assertIsNone(result['arithmetic_pass'])
        self.assertNotIn('error_type',result)

    def test_readout_does_not_count_multivisible_or_failed_as_pass(self):
        rows=[dict(mode='image',mask='default',returncode=0,probe=dict(cuinit_rc=0,visible_devices=8,uuids=['a']*8,arithmetic_pass=None)),
              dict(mode='image',mask='default',returncode=0,probe=dict(cuinit_rc=999)),
              dict(mode='image',mask='default',returncode=0,probe=dict(cuinit_rc=0,visible_devices=1,uuids=['b'],arithmetic_pass=True))]
        result=summarize(rows)
        self.assertEqual(result['single_device_pass_counts']['image-default'],1)
        self.assertEqual(result['unique_single_device_uuids']['image-default'],1)
        self.assertEqual(result['cuinit_status_counts']['image-default'],{'0':2,'999':1})


if __name__=='__main__':unittest.main()
