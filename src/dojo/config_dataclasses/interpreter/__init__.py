# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from dojo.utils.config import LazyFactory

INTERPRETER_MAP = {
    "PythonInterpreterConfig": LazyFactory("dojo.core.interpreters.python", "PythonInterpreter"),
    "JupyterInterpreterConfig": LazyFactory(
        "dojo.core.interpreters.jupyter.jupyter_interpreter", "JupyterInterpreterFactory"
    ),
}
