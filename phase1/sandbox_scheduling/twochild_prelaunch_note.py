"""Pre-outcome correction of inherited prose; immutable plan/runtime unchanged."""
import datetime
import json
import sys
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/scheduling-live-twochild-20261010-v1')


def corrected_prose(plan):
    if plan['run_seconds']!=1500 or plan['candidate_timeout_seconds']!=240:
        raise ValueError('wrong scientific budget')
    corrected={}
    for field in ('common_adapter','primary'):
        if plan[field].count('600s')!=1:
            raise ValueError('unexpected inherited prose')
        corrected[field]=plan[field].replace('600s','1500s')
    return corrected


def main():
    sys.path.insert(0,str(ROOT))
    import live_twochild_20261010 as entry
    from lifecycle_pilot import read,write,sha
    if any((ROOT/name).exists() for name in ('submit-intent.json','launch.json')):
        raise ValueError('prelaunch only; no post-outcome correction')
    plan=entry.t.check()
    pin=sha(ROOT/'plan.json')
    if read(ROOT/'preflight.json')['plan_sha256']!=pin:
        raise ValueError('preflight pin')
    for row in plan['schedule']:
        cfg=read(ROOT/f'configs/{row["index"]}.json')
        if cfg['solver']['num_children']!=2 or cfg['solver']['time_limit_secs']!=1500:
            raise ValueError('native config budget')
    runtime=entry.host()
    if runtime.SECONDS!=1500:
        raise ValueError('actual native deadline')
    note=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        plan_sha256=pin,source_commit=plan['source_commit'],
        correction=corrected_prose(plan),
        reason='Two descriptive strings inherited 600s; numeric plan, configs, prompt and execution deadline were already1500s before preparation.',
        changed_runtime_or_inputs=False,results_observed=False,
        checked_configs=len(plan['schedule']),checked_runtime_seconds=runtime.SECONDS)
    write(ROOT/'prelaunch-prose-correction.json',note)
    print(json.dumps(note,sort_keys=True))


if __name__=='__main__':main()
