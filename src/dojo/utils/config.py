# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.


import importlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LazyFactory:
    module: str
    attribute: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        factory = getattr(importlib.import_module(self.module), self.attribute)
        return factory(*args, **kwargs)


def build(cfg, cfg_obj_map, **kwargs):
    return cfg_obj_map[cfg.__class__.__name__](cfg, **kwargs)
