"""Read-only template preview during width run; not successor production approval."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from forets_environment_build_20260912 import read,write,encode,sha
from forets_execution_memory_20260913 import frozen_memory,apply_memory

def run(parent):
    parent=parent.resolve(strict=True);artifact=read(parent/'artifact.json');prior=read(parent/'prepared.json')
    if artifact['source_tree']!='cda5e378046811fa20eadc7bc9a0d2343e69ddca':raise ValueError('exact current source only')
    stage=Path(__file__).resolve().parent
    memory=frozen_memory(stage/'closed-error-families.json',stage/'closed-error-recurrence.json')
    with tempfile.TemporaryDirectory(prefix='memory-prompt-preview-',dir=stage) as temp:
        root=Path(temp);(root/'configs').mkdir();(root/'source').symlink_to(parent/'source',target_is_directory=True)
        (root/'code').symlink_to(parent/'code',target_is_directory=True)
        write(root/'artifact.json',encode(artifact));write(root/'frozen-memory.json',encode(memory));rows=[]
        for task in ('leaf-classification','spaceship-titanic'):
            p=next(r for r in prior['run_configs'] if r['task']==task and r['arm']=='direct_two')
            original=read(parent/'configs'/(p['run_id']+'.json'),p['config_sha256'])
            for seed in (40,41):
                for arm in ('no_memory','execution_memory'):
                    rid=task+'-s'+str(seed)+'-'+arm;cfg=apply_memory(copy.deepcopy(original),memory,arm=='execution_memory')
                    cfg['metadata']['seed']=cfg['solver']['selector_seed']=seed
                    digest=write(root/'configs'/(rid+'.json'),encode(cfg))
                    rows.append(dict(run_id=rid,task=task,seed=seed,arm=arm,config_sha256=digest))
        write(root/'prepared.json',encode(dict(run_configs=rows)))
        from verify_memory_prompt_integration_20260913 import run as verify
        verify(root)
        result=read(root/'memory-prompt-integration.json')
        result['status']='PREVIEW_ON_WIDTH_SOURCE_NOT_SUCCESSOR_APPROVAL'
        print(json.dumps(dict(status=result['status'],actual_operator_calls=result['actual_operator_calls'],
            sha256=write(stage/'memory-prompt-preview.json',encode(result)))))

if __name__=='__main__':run(Path(sys.argv[1]))
