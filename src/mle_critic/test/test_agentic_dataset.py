"""Check actual selected pairs, reproducibility, code/label alignment and run split."""
from collections import Counter
import json

from src.mle_critic.src.agentic.build_dataset import build_records, DATA, PROJECT_ROOT
from src.mle_critic.src.agentic.common import TASKS
from src.mle_critic.src.postprocess.rl.build_judger_messages import read_cards


def test_selected_dataset():
    pairs_path = DATA / "batch_value_pairs_selected_filtered_runsplit.jsonl"
    cards_path = DATA / "augmented_cards_current.json"
    args = (pairs_path, cards_path, PROJECT_ROOT / "data/mlebench")
    records = build_records(*args)
    assert records == build_records(*args)
    cards = read_cards(str(cards_path))
    pairs = [json.loads(line) for line in pairs_path.read_text().splitlines() if line.strip()]
    rows = records["train"] + records["test"]
    assert len(rows) == len(pairs)
    assert {row["task"] for row in rows} == TASKS
    assert len({row["sample_uuid"] for row in rows}) == len(rows)
    labels = Counter(row["reward_model"]["ground_truth"] for row in rows)
    assert .45 < labels["A"] / len(rows) < .55
    for row in rows:
        pair = pairs[row["extra_info"]["index"]]
        label = row["reward_model"]["ground_truth"]
        other = "B" if label == "A" else "A"
        assert row[f"solution_{label}"] == cards[pair["better"]]["code"]
        assert row[f"solution_{other}"] == cards[pair["worse"]]["code"]
        assert row["extra_info"]["split"] == pair["intask_split"]
        assert all("gap_raw" not in m["content"] and pair["better"] not in m["content"] for m in row["prompt"])
