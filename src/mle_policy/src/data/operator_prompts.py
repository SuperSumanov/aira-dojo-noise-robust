"""The system message each dojo operator sends, read from its config file.

The OpenAI-protocol clients recorded the whole prompt in a single ``system``
turn, so those samples kept only the rendered user message.  The SFT view needs
``[system, user, assistant]``, so the system message is restored from the same
config file dojo loads; rows that already carry a real system message are left
alone (and their text is identical to the config, which is what makes the two
groups consistent).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

# <repo>/src/dojo/configs/solver/operators/mlebench
CONFIG_ROOT = (
    Path(__file__).resolve().parents[4] / "src" / "dojo" / "configs" / "solver" / "operators" / "mlebench"
)

# Data operator -> (config directory, key inside the yaml).  ``analysis`` is
# spelled ``analyze`` in the config and ships with the "aide" operator set; the
# other four exist in both sets with the same system message.
OPERATOR_CONFIGS = {
    "draft": ("aira_operators", "draft"),
    "debug": ("aira_operators", "debug"),
    "improve": ("aira_operators", "improve"),
    "crossover": ("aira_operators", "crossover"),
    "analysis": ("aide_operators", "analyze"),
}


@lru_cache(maxsize=None)
def system_message(operator: str) -> str:
    """The system message the config of ``operator`` sends, e.g. for ``draft``."""
    if operator not in OPERATOR_CONFIGS:
        raise KeyError(f"no dojo operator config for {operator!r}, known: {sorted(OPERATOR_CONFIGS)}")
    directory, key = OPERATOR_CONFIGS[operator]
    path = CONFIG_ROOT / directory / f"{key}.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return config[key]["system_message_prompt_template"]["template"]
