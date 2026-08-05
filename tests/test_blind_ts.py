from dojo.core.solvers.utils.journal import Journal
from dojo.core.solvers.utils.metric import WorstMetricValue
from dojo.solvers.blind_ts import BlindTS
from dojo.solvers.mcts.mcts import MCTSNode


def _node(ctime: float, parent: MCTSNode | None = None) -> MCTSNode:
    return MCTSNode(
        code="",
        ctime=ctime,
        parents=[] if parent is None else [parent],
        metric=WorstMetricValue(maximize=True),
        is_buggy=True,
    )


def test_search_policy_selects_globally_oldest_leaf() -> None:
    solver = BlindTS.__new__(BlindTS)
    solver.journal = Journal()

    root = _node(0)
    first_branch = _node(1, root)
    second_branch = _node(2, root)
    first_branch_leaf = _node(3, first_branch)
    for node in (root, first_branch, second_branch, first_branch_leaf):
        solver.journal.append(node)

    assert solver.search_policy(root) == [root, second_branch]

    second_branch_leaf = _node(4, second_branch)
    solver.journal.append(second_branch_leaf)

    assert solver.search_policy(root) == [root, first_branch, first_branch_leaf]
