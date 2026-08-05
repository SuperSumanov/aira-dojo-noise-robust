# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass, field

from omegaconf import MISSING

from dojo.config_dataclasses.solver.base import SolverConfig


@dataclass
class BlindTSSolverConfig(SolverConfig):
    num_children: int = field(
        default=MISSING, metadata={"description": "Number of child nodes expanded per search step"}
    )
    max_debug_depth: int = field(default=MISSING, metadata={"description": "Maximum depth of debugging analysis"})
    max_debug_time: float = field(
        default=MISSING, metadata={"description": "Maximum time allowed for debugging analysis"}
    )
    data_preview: bool = field(
        default=MISSING,
        metadata={"description": "Whether to provide the agent with a preview of the data before execution"},
    )

    def validate(self) -> None:
        super().validate()
