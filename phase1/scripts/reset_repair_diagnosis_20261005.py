"""Read closed development diagnostics; emit only public schema and fixed flags."""
import json,re,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/implementation-reset-20261005-v1')
sys.path.insert(0,str(R))
from implementation_reset_20261005 import native, read
assert (R/'closed.json').exists()
native().setup()
from dojo.config_dataclasses.run import RunConfig
from dojo.tasks.mlebench.task import MLEBenchTask
rows=[]
for i in range(4):
    cfg=RunConfig.load_from_json(R/'configs'/f'{i}.json')
    task=MLEBenchTask(cfg.task)
    if i<2:
        assert not task.private_dir.exists()
        print(json.dumps({'task':cfg.task.name,'public_dir':str(task.public_dir),'public_description':task.task_description}))
    for p in sorted((R/f'episode-{i}').glob('action-*/generation.private.json')):
        g=read(p);messages=g['info']['prompt_messages']
        t='\n'.join(str(m.get('content','')) for m in messages)
        t=re.sub(r'\x1b\[[0-9;]*m','',t)
        flags={name:bool(re.search(pattern,t,re.I)) for name,pattern in {
            'forced_5fold':'USE 5-FOLD|PRINTS THE 5-FOLD',
            'different_idea':'DIFFERENT ASPECT|different from those previously explored',
            'debug_preserve_previous':'Do NOT.*alter the core method',
            'sparse_dtype_error':'dtype.*float32|dtype.*float64|int32|int64',
            'empty_vocabulary':'empty vocabulary',
            'unknown_label':'Unknown label type',
            'feature_name_special_json':'special JSON characters|special.*feature name',
            'sparse_format_error':'Only.*sparse|sparse.*matrix|sparse.*dtype',
            'inconsistent_samples':'inconsistent numbers of samples',
            'solver_option_error':'solver.*not support|Unsupported set of arguments',
        }.items()}
        rows.append({'index':i,'action':p.parent.name,'flags':flags})
print(json.dumps({'closed_diagnostic':rows}))
