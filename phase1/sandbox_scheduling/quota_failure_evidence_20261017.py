"""Preserve failed19004 readout; export credential-scanned structural evidence.

Never changes the plan, source, failed readout, success gate or any Slurm job.
Only the already closed DEV batch is allowed. No candidate code/labels exported.
"""
import hashlib
import inspect
import json
import re
import sys
from pathlib import Path

R = Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v1')
PIN = 'f08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9'
RX = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    b = Path(p).read_bytes()
    if RX.search(b): raise ValueError('credential-shaped input refused')
    return json.loads(b)


def main():
    assert sha(R/'plan.json') == PIN
    plan = read(R/'plan.json'); closed = read(R/'closed.json')
    assert closed['complete'] == 32 and closed['error'] is None
    assert all(sha(R/n) == h for n,h in plan['files'].items())
    prior = R/'readout-20261017-v1'
    assert prior.is_dir() and not (prior/'summary.json').exists()
    original_hashes = {p.name: sha(p) for p in prior.iterdir() if p.is_file()}
    out = R/'failure-audit-20261017-v1'; out.mkdir(mode=0o700)
    def write(name, value):
        raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode()
        assert not RX.search(raw)
        with (out/name).open('xb') as f: f.write(raw)
    for name in ('runs.json','effort.json','input-checks.json'):
        write(name, read(prior/name))
    for b in range(4):
        events = []
        for line in (R/f'generation-{b}/events.jsonl').read_bytes().splitlines():
            if RX.search(line): raise ValueError('credential-shaped event refused')
            e = json.loads(line)
            if e['event'] not in ('queued','admitted','released','cancelled'): continue
            item = {k:e[k] for k in ('event','time','key') if k in e}
            if e['event'] == 'queued': item['request'] = {k:e['request'][k] for k in ('key','task','role','requested','run')}
            events.append(item)
        write(f'generation-{b}.json', events)
        queues = [read_json_line(x) for x in (R/f'pool-{b}/events.jsonl').read_bytes().splitlines()]
        write(f'queue-{b}.json', queues)
    # Importing the frozen entry constructs function bindings only. Never call
    # host.setup/worker/install or initialize a model/kernel for this observation.
    sys.path.insert(0, str(R))
    import generation_quota_trial_20261017 as trial
    entry = trial.host()
    def identity(f): return dict(module=f.__module__,qualname=f.__qualname__,source_file=Path(f.__code__.co_filename).name,
        source_line=f.__code__.co_firstlineno,code_names=list(f.__code__.co_names),
        source_sha256=hashlib.sha256(inspect.getsource(f).encode()).hexdigest())
    aliases = dict(advertised=identity(trial.common.original.install_hooks),
        runtime=identity(entry.install_hooks),deep_dispatch=identity(trial.common.original.base.c.trial.install_hooks),
        runtime_is_advertised=entry.install_hooks is trial.common.original.install_hooks,
        runtime_is_deep_dispatch=entry.install_hooks is trial.common.original.base.c.trial.install_hooks,
        worker_resolves_runtime_binding=entry.worker.__globals__['install_hooks'] is entry.install_hooks,
        no_setup_or_worker_called=True,model_calls=0,gpu_calls=0)
    write('hook-bindings.json', aliases)
    write('closure.json', dict(assigned=32,complete=closed['complete'],job='19004',node='gpu3',
        elapsed_seconds=5096,gpus=6,gpu_seconds=5096*6,plan_sha256=PIN,source_commit=plan['source_commit'],
        original_readout_failed=True,original_readout_preserved_sha256=original_hashes,
        failure='generation_audit: actual admitted key differs from globally highest-priority eligible request',
        original_success_gate_met=False,quality_comparison_valid=False,
        limits=['No pass is imputed for an unexecuted treatment.','This is a post-failure structural diagnosis, not a replacement readout.']))
    assert original_hashes == {p.name:sha(p) for p in prior.iterdir() if p.is_file()}
    print(json.dumps(dict(directory=str(out),files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size,credential_shape_hits=0)
        for p in sorted(out.iterdir())},hook_bindings=aliases),sort_keys=True))


def read_json_line(b):
    assert not RX.search(b)
    return json.loads(b)


if __name__ == '__main__': main()
