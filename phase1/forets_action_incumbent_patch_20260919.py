"""Common (both arms) per-action incumbent saving for a future full run.

This does not select by external grade. It invokes the existing native journal
selector after each executed-and-analyzed action rather than after a whole batch.
No files are written by this builder; existing experiments are never patched.
"""
import ast,hashlib
from forets_ready_batch_patch_20260919 import once
from forets_ready_runtime_patch_20260919 import CONFIG,RUNTIME,LEDGER,EXPECTED,patched_sources

MCTS='src/dojo/solvers/mcts/mcts.py'
WALLCLOCK='src/dojo/solvers/fore_ts/wallclock.py'
EXPECTED_EXTRA={MCTS:'f81203004ca873cc46a958a1fb9eba3b8dfabe5531f290453bcfc6f523f594d0',
                WALLCLOCK:'a2f9597ab6670dd4e97b4c3ab88a656cd1f6de8bfc9060f61926c8f9c87a2b0c'}

def build(sources):
    if set(sources)!=set(EXPECTED)|set(EXPECTED_EXTRA):raise ValueError('exact source set')
    original={k:v.replace('\r\n','\n') for k,v in sources.items()}
    for path,expected in {**EXPECTED,**EXPECTED_EXTRA}.items():
        if hashlib.sha256(original[path].encode()).hexdigest()!=expected:raise ValueError('unreviewed source')
    result=patched_sources({k:original[k] for k in EXPECTED})
    runtime=result[RUNTIME].decode()
    runtime=once(runtime,'            solver.state.current_step += 1\n',
        '            solver.state.current_step += 1\n'
        '            from dojo.solvers.fore_ts.wallclock import checkpoint_incumbent\n'
        '            checkpoint_incumbent(solver)\n')
    mcts=once(original[MCTS],
        '            from dojo.solvers.fore_ts.wallclock import checkpoint_incumbent\n            checkpoint_incumbent(self)\n','')
    mcts=once(mcts,'            self.state.current_step += 1\n            debug_path.append(buggy_node)\n',
        '            self.state.current_step += 1\n'
        '            from dojo.solvers.fore_ts.wallclock import checkpoint_incumbent\n'
        '            checkpoint_incumbent(self)\n'
        '            debug_path.append(buggy_node)\n')
    wall=once(original[WALLCLOCK],"selection='original_journal_get_best_node_after_complete_iteration'",
        "selection='original_journal_get_best_node_after_executed_analyzed_action'")
    result.update({RUNTIME:runtime.encode(),MCTS:mcts.encode(),WALLCLOCK:wall.encode()})
    for value in result.values():ast.parse(value)
    return result
