"""Interpreter/build metadata only; no CUDA context or model initialization."""
import json,sys
import torch
print(json.dumps(dict(executable=sys.executable,torch_version=torch.__version__,cuda_build=torch.version.cuda)))
