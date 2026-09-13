"""Explicit opt-in only; the ordinary Jupyter configuration remains unchanged."""
from dataclasses import dataclass, field
import math

from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig


@dataclass
class FreshContainerInterpreterConfig(JupyterInterpreterConfig):
    container_runtime: str = field(default="singularity")

    def validate(self) -> None:
        super().validate()
        if self.container_runtime != "singularity":
            raise ValueError("fresh-container backend requires the verified singularity runtime")
        if (isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float))
                or not math.isfinite(self.timeout) or self.timeout <= 0):
            raise ValueError("fresh-container timeout must be positive and finite")
