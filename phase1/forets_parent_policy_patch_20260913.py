"""Undeployed parent-only control; never edits an active source tree.

This is a greedy incumbent reference, not a novel method. A future matrix
must fix the generator, operator set, candidate selector and all budgets.
"""
from pathlib import Path
from forets_paid_patch_20260911 import once


def patched_sources(config_text, solver_text):
    config_text = once(config_text,
        '    common_start_protocol: str = "none"',
        '    common_start_protocol: str = "none"\n    parent_selection_policy: str = "uct_leaf"')
    config_text = once(config_text,
        '        if self.common_start_protocol not in ("none", "rf_common_v1"):',
        '        if self.parent_selection_policy not in ("uct_leaf", "incumbent"):\n'
        '            raise ValueError("parent selection policy")\n'
        '        if self.common_start_protocol not in ("none", "rf_common_v1"):')
    # Placed inside the actual class, preserving its initialization and operators.
    # Locate its first method rather than its docstring for a stable insertion.
    marker = '    def __init__('
    method = '''    def search_policy(self, root_node):
        policy = self.cfg.parent_selection_policy
        if policy == "uct_leaf":
            return super().search_policy(root_node)
        if policy != "incumbent":
            raise ValueError("parent selection policy")
        from dojo.solvers.fore_ts.incumbent_parent import incumbent_path
        return incumbent_path(root_node, self.journal)

'''
    solver_text = once(solver_text, marker, method + marker)
    return {
        'src/dojo/config_dataclasses/solver/fore_ts.py': config_text.encode(),
        'src/dojo/solvers/fore_ts/fore_ts.py': solver_text.encode(),
        'src/dojo/solvers/fore_ts/incumbent_parent.py': Path(__file__).with_name(
            'forets_incumbent_parent_reference_20260913.py').read_bytes().replace(b'\r\n', b'\n'),
    }
