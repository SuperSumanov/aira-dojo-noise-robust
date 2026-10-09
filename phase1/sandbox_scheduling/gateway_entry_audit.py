"""Read-only audit of whether the intended observation entry actually ran."""
import json
from pathlib import Path
import readiness_gateway_trial as wrapper

rows=[]
for i in range(48):
    ep=wrapper.trial.R/f'episode-{i}'
    raw=(ep/'worker.private.log').read_text(encoding='utf-8',errors='replace')
    rows.append(dict(index=i,observer_marker_in_command='runpy.run_path' in raw and 'gateway_counter.py' in raw,
                     old_bootstrap_in_command="runpy.run_module('jupyter'" in raw,
                     counter_exists=(ep/'work/gateway-counts.json').exists()))
wrapper.runtime()
from dojo.core.interpreters.jupyter import singularity_jupyter_server as server
print(json.dumps(dict(rows=rows,
    loaded_bootstrap_is_observer='gateway_counter.py' in server._JUPYTER_BOOTSTRAP,
    function_global_is_observer='gateway_counter.py' in server._build_singularity_command.__globals__['_JUPYTER_BOOTSTRAP'],
    wrapper_file=wrapper.__file__,trial_root=str(wrapper.trial.R))))
