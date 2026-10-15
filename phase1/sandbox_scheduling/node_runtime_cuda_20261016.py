"""Real CUDA arithmetic without datasets, models, scoring, or network access."""
import ctypes
import json
import os
import uuid
import torch

lib = ctypes.CDLL('libcuda.so.1')
assert lib.cuInit(0) == 0
count = ctypes.c_int()
assert lib.cuDeviceGetCount(ctypes.byref(count)) == 0 and count.value == 1
raw = (ctypes.c_ubyte * 16)()
device = ctypes.c_int()
assert lib.cuDeviceGet(ctypes.byref(device), 0) == 0
assert lib.cuDeviceGetUuid(ctypes.byref(raw), device) == 0
identity = 'GPU-'+str(uuid.UUID(bytes=bytes(raw)))
assert identity == os.environ['EXPECTED_GPU_UUID']
assert torch.cuda.is_available() and torch.cuda.device_count() == 1
torch.manual_seed(216001)
x = torch.ones((128, 128), device='cuda', dtype=torch.float32)
y = x @ x
torch.cuda.synchronize()
assert bool(torch.all(y == 128).item())
print('PROBE_JSON='+json.dumps(dict(passed=True, gpu_uuid=identity,
      gpu_name=torch.cuda.get_device_name(0), capability=torch.cuda.get_device_capability(0),
      torch_version=torch.__version__, cuda_version=torch.version.cuda,
      seed=216001, matrix_shape=[128,128], exact_result=128)), flush=True)
