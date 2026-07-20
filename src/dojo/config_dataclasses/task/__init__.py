# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from dojo.utils.config import LazyFactory

TASK_MAP = {"MLEBenchTaskConfig": LazyFactory("dojo.tasks.mlebench.task", "MLEBenchTask")}
