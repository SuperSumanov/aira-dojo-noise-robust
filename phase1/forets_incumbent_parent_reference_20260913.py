"""Undeployed greedy-parent reference; use only search-visible journal metric.

This is an existing-style baseline, not a novel algorithm or efficacy claim.
It must not be inserted into either active arm mid-experiment.
"""


def incumbent_path(root,journal):
    node=journal.get_best_node()
    if node is None:
        return [root]
    if node.is_buggy is not False:
        raise ValueError('journal selected a buggy incumbent')
    reverse=[];seen=set()
    while True:
        if id(node) in seen:raise ValueError('cyclic parent chain')
        seen.add(id(node));reverse.append(node)
        if node is root:break
        if len(node.parents)!=1:raise ValueError('non-tree or disconnected incumbent')
        node=node.parents[0]
    return list(reversed(reverse))
