from dataclasses import dataclass

from dojo.config_dataclasses.operators.base import OperatorConfig


@dataclass
class WarmupAnalyzeOperatorConfig(OperatorConfig):
    """Select the separate warmup-aware analysis operator."""
