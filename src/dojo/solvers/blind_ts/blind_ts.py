# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, cast

from dojo.solvers.mcts.mcts import MCTS, MCTSNode


class BlindTS(MCTS):
    """Tree search that expands leaves in first-created, first-expanded order."""

    search_name = "BlindTS"

    def search_policy(self, root_node: MCTSNode) -> List[MCTSNode]:
        leaves = [node for node in self.journal.nodes if node.is_leaf]
        if not leaves:
            raise RuntimeError("Blind tree search has no leaf node to expand")

        leaf = min(
            leaves,
            key=lambda node: (
                node.ctime,
                node.step if node.step is not None else float("inf"),
            ),
        )

        reverse_path: list[MCTSNode] = []
        current = cast(MCTSNode, leaf)
        while True:
            reverse_path.append(current)
            if current is root_node:
                break
            if len(current.parents) != 1:
                raise RuntimeError(
                    f"Cannot reconstruct path for node {current.id}: expected exactly one parent"
                )
            current = cast(MCTSNode, current.parents[0])

        return list(reversed(reverse_path))
