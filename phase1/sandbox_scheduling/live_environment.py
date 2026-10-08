"""Host dependency receipt only; never enumerate or export environment values."""
import argparse
import importlib.metadata
from pathlib import Path
import platform
import sys
from lifecycle_pilot import read,write,sha

def capture(root):
    root=Path(root)
    plan=read(root/'plan.json')
    if len(plan['schedule'])!=16 or plan['gpus']!=3:raise ValueError('wrong batch')
    distributions=('torch','numpy','pandas','scikit-learn','litellm','openai',
                   'pydantic','omegaconf','hydra-core','jupyter-client','websocket-client')
    versions={name:importlib.metadata.version(name) for name in distributions}
    receipt=dict(plan_sha256=sha(root/'plan.json'),python=sys.version,platform=platform.platform(),
                 host_packages=versions,task_image_sha256=plan['task_image_sha256'],
                 service_image_sha256=plan['service_image_sha256'],
                 no_model_calls=True,no_gpu_execution=True)
    target=root/'host-environment.json'
    if target.exists():
        if read(target)!=receipt:raise ValueError('environment changed since preparation')
    else:write(target,receipt)
    print('HOST_ENVIRONMENT_RECEIPT_OK')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');capture(parser.parse_args().root)
