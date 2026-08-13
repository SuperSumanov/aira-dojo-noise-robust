"""Regression tests for Bradley--Terry checkpoint selection."""

import pytest

pytest.importorskip("transformers")

from src.mle_critic.src.train.config.bradley_terry_config import BradleyTerryConfig


def test_pair_accuracy_is_maximized_for_best_checkpoint(tmp_path) -> None:
    config = BradleyTerryConfig(
        pairs="unused-pairs.jsonl",
        cards="unused-cards.jsonl",
        output_dir=str(tmp_path),
        report_to=[],
        bf16=False,
        use_cpu=True,
    )

    assert config.metric_for_best_model == "eval_pair_accuracy"
    assert config.greater_is_better is True
