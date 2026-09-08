# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass, field

from omegaconf import MISSING

from dojo.config_dataclasses.solver.mcts import MCTSSolverConfig


@dataclass
class ForeTSSolverConfig(MCTSSolverConfig):
    critic_host: str = field(
        default=MISSING, metadata={"description": "Host address for the critic service"}
    )
    critic_port: int = field(
        default=MISSING, metadata={"description": "Port number for the critic service"}
    )
    critic_max_attempts: int = field(
        default=MISSING, metadata={"description": "Maximum number of attempts to contact the critic service"}
    )
    critic_top_k: int = field(
        default=MISSING, metadata={"description": "Number of top candidates to consider from the critic's output"}
    )
    num_children_to_choose: int = field(
        default=MISSING, metadata={"description": "Number of child nodes to choose based on critic's evaluation"}
    )

    def validate(self) -> None:
        super().validate()
