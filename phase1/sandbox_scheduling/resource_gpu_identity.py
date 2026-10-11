"""CUDA driver identity inside the actual process/cgroup; never trusts indices."""
import ctypes
import uuid


def gpu_uuids(expected):
    lib=ctypes.CDLL('libcuda.so.1')
    if lib.cuInit(0)!=0:raise RuntimeError('CUDA driver initialization failed')
    count=ctypes.c_int()
    if lib.cuDeviceGetCount(ctypes.byref(count))!=0 or count.value!=expected:
        raise RuntimeError('unexpected visible CUDA device count')
    result=[]
    for i in range(expected):
        device=ctypes.c_int();raw=(ctypes.c_ubyte*16)()
        if lib.cuDeviceGet(ctypes.byref(device),i)!=0 or lib.cuDeviceGetUuid(ctypes.byref(raw),device)!=0:
            raise RuntimeError('CUDA identity query failed')
        result.append('GPU-'+str(uuid.UUID(bytes=bytes(raw))))
    return result
