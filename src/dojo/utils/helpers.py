# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import os
import json
from pathlib import Path


def write_env_variables_to_json(output_dir):
    """
    Write the environment variables to a JSON file.
    """
    # Path to file
    output_file = Path(output_dir) / "env_variables.json"

    # Convert the environment variables to a dictionary.
    # Secret-looking values are redacted before the dump: run directories are exactly
    # what gets shared and published, and this file used to carry the raw API keys.
    import hashlib
    import re
    keypat = re.compile(r"(key|token|secret|passwd|password|credential)", re.I)
    valpat = re.compile(r"^(sk-|hf_|ghp_|gho_|glpat-|xoxb-|AKIA)[A-Za-z0-9._\-]{8,}")
    env_vars = {}
    for k, v in os.environ.items():
        if isinstance(v, str) and v and (keypat.search(k) or valpat.match(v)):
            env_vars[k] = "REDACTED:sha256:" + hashlib.sha256(v.encode()).hexdigest()[:8]
        else:
            env_vars[k] = v

    # Write the dictionary to a JSON file
    with open(output_file, "w") as file:
        json.dump(env_vars, file, indent=4)

    print("Environment variables written as JSON to env_variables.json")
