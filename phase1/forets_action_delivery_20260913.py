"""Opt-in passive per-action delivery; separate from original iteration result."""
import hashlib
import json
import math
from pathlib import Path
import time


PROTOCOL='original_search_visible_action_delivery_v1'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def observed_nodes(journal):
    """Only search-visible fields needed to independently replay selection."""
    rows=[]
    for node in journal.nodes:
        if node.step==0 and node.code=='' and not node.parents:
            continue
        if (type(node.step) is not int or node.step<1 or node.exec_time is None
            or type(node.exec_time) not in (int,float) or not math.isfinite(node.exec_time)
            or node.exec_time<0 or type(node.exit_code) is not int or type(node.is_buggy) is not bool):
            raise ValueError('fully executed and parsed nodes required')
        value=node.metric.value
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value)):
            raise ValueError('finite search metric')
        if node.metric.maximize is not None and type(node.metric.maximize) is not bool:
            raise ValueError('metric direction')
        rows.append(dict(node_id=str(node.id),step=node.step,code_sha256=digest(node.code.encode()),
            execution_seconds=node.exec_time,exit_code=node.exit_code,is_buggy=node.is_buggy,
            search_value=value,maximize=node.metric.maximize))
    if len({r['node_id'] for r in rows})!=len(rows):raise ValueError('duplicate node')
    return rows


def record_action(solver, wallclock, *, clock_ns=time.monotonic_ns):
    if getattr(solver.cfg,'action_delivery_protocol','none')=='none':return None
    if solver.cfg.action_delivery_protocol!=PROTOCOL:raise ValueError('unknown delivery protocol')
    if solver.cfg.use_test_score is not False:raise ValueError('search-visible only')
    spec=wallclock.budget()
    if spec is None:raise ValueError('bounded execution required')
    start,deadline,base=spec
    observed=clock_ns()
    if observed<start:raise ValueError('clock origin')
    if observed>=deadline:return None
    rows=observed_nodes(solver.journal)
    if not rows:return None  # The normal create_root_node call is not an action.
    node=solver.journal.get_best_node()
    receipt=None
    if node is not None:
        if id(node) not in {id(n) for n in solver.journal.nodes}:raise ValueError('chosen node not observed')
        stored=wallclock._nodes.get(id(node))
        if stored is None or stored[0] is not node:raise ValueError('exact execution association absent')
        receipt=dict(stored[1])
        if receipt['code_sha256']!=digest(node.code.encode()):raise ValueError('selected code drift')
    directory=base/'action-incumbents'
    if directory.is_symlink():raise ValueError('delivery symlink')
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    # Length is an action sequence, not a candidate quality or test-based filter.
    action=len(rows)
    data=directory/f'action-{action:06d}.json'
    value=dict(schema=1,protocol=PROTOCOL,action=action,current_step=solver.state.current_step,
        start_ns=start,deadline_ns=deadline,observation_ns=observed,observed_nodes=rows,
        node_id=str(node.id) if node is not None else None,code=node.code if node is not None else None,
        submission=receipt,selection='original_journal_get_best_node_after_parsed_action')
    raw=wallclock.encode(value)
    wallclock.write_private(data,raw)
    durable=clock_ns()
    if durable<observed:raise ValueError('clock reversal')
    commit=dict(schema=1,data_file=data.name,data_sha256=digest(raw),durable_ns=durable,
        deadline_ns=deadline,eligible=durable<deadline)
    wallclock.write_private(directory/f'action-{action:06d}.commit.json',wallclock.encode(commit))
    return commit


def patch_sources(config,solver):
    if 'action_delivery_protocol' in config or '    def log_journal(self):' in solver:
        raise ValueError('delivery already present or log hook changed')
    def once(text,old,new):
        if text.count(old)!=1:raise ValueError('exact source anchor')
        return text.replace(old,new)
    config=once(config,'    common_start_protocol: str = "none"',
        '    common_start_protocol: str = "none"\n    action_delivery_protocol: str = "none"')
    config=once(config,'        if self.common_start_protocol not in ("none", "rf_common_v1"):',
        '        if self.action_delivery_protocol not in ("none", "'+PROTOCOL+'"):\n'
        '            raise ValueError("action delivery protocol")\n'
        '        if self.common_start_protocol not in ("none", "rf_common_v1"):')
    solver=once(solver,'    def load_checkpoint(self):',
        '    def log_journal(self):\n'
        '        result = super().log_journal()\n'
        '        if self.cfg.action_delivery_protocol != "none":\n'
        '            from dojo.solvers.fore_ts.action_delivery import record_action\n'
        '            from dojo.solvers.fore_ts import wallclock\n'
        '            record_action(self, wallclock)\n'
        '        return result\n\n'
        '    def load_checkpoint(self):')
    return config,solver
