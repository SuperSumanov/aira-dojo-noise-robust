"""Import/shape test of the real remote native stack, no subprocess/model/kernel."""
import json
from unittest.mock import patch
import subprocess


def forbidden(*a,**kw):raise AssertionError('CPU import must not start external process')


with patch.object(subprocess,'Popen',forbidden):
    import diverse_trial_20261017 as trial
    rows=trial.schedule()
    assert len(rows)==48 and {r['index'] for r in rows}==set(range(48))
    assert [r['pool_mode'] for r in rows[::8]]==list(trial.ORDER)
    groups={}
    for r in rows:groups.setdefault((r['task'],r['seed']),[]).append(r['pool_mode'])
    assert len(groups)==16 and all(sorted(v)==['colocated','diverse','shared'] for v in groups.values())
    # Second module import is how the prepared container shim is actually used.
    import importlib.util
    spec=importlib.util.spec_from_file_location('diverse_second_import',trial.__file__)
    other=importlib.util.module_from_spec(spec);spec.loader.exec_module(other)
    assert other.schedule()==rows
    assert not trial.R.exists(),'CPU import check is before actual package preparation'
print(json.dumps(dict(passed=True,assigned=48,paired_groups=16,modes=list(trial.ORDER),
    import_twice=True,external_processes=0,model_calls=0,gpu_calls=0)))
