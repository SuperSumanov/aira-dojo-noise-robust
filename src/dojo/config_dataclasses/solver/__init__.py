# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from dojo.utils.config import LazyFactory

SOLVER_MAP = {
    "BlindTSSolverConfig": LazyFactory("dojo.solvers.blind_ts", "BlindTS"),
    "GreedySolverConfig": LazyFactory("dojo.solvers.greedy", "Greedy"),
    "MCTSSolverConfig": LazyFactory("dojo.solvers.mcts", "MCTS"),
    "EvolutionarySolverConfig": LazyFactory("dojo.solvers.evo", "Evolutionary"),
}
