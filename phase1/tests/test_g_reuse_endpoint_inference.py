import hashlib
import json

import pytest
import torch

from phase1.g_reuse_endpoint_inference import (
    EncodedEndpoint, EndpointInferenceError, SCORE_KEYS,
    assemble_score_matrix, encode_endpoints, score_endpoints,
)
from phase1.materialize_g_reuse_blinded_margins import materialize, write
from phase1.verify_g_reuse_blinded_margins import verify
from pathlib import Path


class Tokenizer:
    def __init__(self):
        self.calls = 0

    def __call__(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        self.calls += 1
        return {"input_ids": [ord(c) % 256 for c in text]}


def cards():
    return [{"endpoint_id": "synthetic:b", "code": "", "task_name": "task"},
            {"endpoint_id": "synthetic:a", "code": "print('测试')\n" * 10, "task_name": "任务"},
            {"endpoint_id": "synthetic:c", "code": "x=1", "task_name": "task"}]


class ScalarModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.scale = torch.nn.Parameter(torch.tensor(1.0))
        self.calls = 0

    def forward(self, input_ids, attention_mask):
        assert not torch.is_grad_enabled() and torch.is_inference_mode_enabled()
        lengths = attention_mask.sum(1)
        for mask, n in zip(attention_mask, lengths):
            assert mask.tolist() == [1] * n.item() + [0] * (len(mask) - n.item())
        self.calls += 1
        return {"logits": self.scale * input_ids[torch.arange(len(input_ids)), lengths - 1].float()}


@pytest.mark.parametrize("max_len", [1, 3, 4, 16, 64, 16384])
def test_rendering_and_truncation(max_len):
    tokenizer = Tokenizer()
    result = encode_endpoints(cards(), tokenizer, max_len=max_len)
    by_id = {x["endpoint_id"]: x for x in cards()}
    assert [r.endpoint_id for r in result] == sorted(by_id)
    for row in result:
        card = by_id[row.endpoint_id]
        raw = [ord(c) % 256 for c in f"# MLE-bench task: {card['task_name']}\n{card['code']}"]
        expected = raw if len(raw) <= max_len else raw[:max_len // 4] + raw[-(max_len - max_len // 4):]
        assert row.input_ids == tuple(expected)
    assert result == encode_endpoints(list(reversed(cards())), tokenizer, max_len=max_len)


@pytest.mark.parametrize("field", ["better", "worse", "label", "outcome", "budget", "intask_split"])
def test_forbidden_extra_card_field_rejected_before_tokenization(field):
    rows = cards()
    rows[-1][field] = "never_read"
    tokenizer = Tokenizer()
    with pytest.raises(EndpointInferenceError, match="blinded_card_schema"):
        encode_endpoints(rows, tokenizer, max_len=64)
    assert tokenizer.calls == 0


@pytest.mark.parametrize("case", ["duplicate", "empty_id", "control_id", "wrong_code", "empty_task", "empty", "bad_context"])
def test_bad_cards(case):
    rows = cards()
    if case == "duplicate": rows.append(rows[0])
    elif case == "empty_id": rows[0]["endpoint_id"] = ""
    elif case == "control_id": rows[0]["endpoint_id"] = "\0"
    elif case == "wrong_code": rows[0]["code"] = 1
    elif case == "empty_task": rows[0]["task_name"] = ""
    elif case == "empty": rows = []
    with pytest.raises(EndpointInferenceError):
        encode_endpoints(rows, Tokenizer(), max_len=0 if case == "bad_context" else 64)


@pytest.mark.parametrize("tokens", [[], [True], [-1], [2**63], [[1]], [1.1]])
def test_bad_tokenizer_tokens(tokens):
    with pytest.raises(EndpointInferenceError):
        encode_endpoints(cards(), lambda *a, **k: {"input_ids": tokens}, max_len=64)


@pytest.mark.parametrize("batch_size", [1, 2, 4])
def test_forward_unique_once_padding_and_no_updates(batch_size):
    rows = (EncodedEndpoint("synthetic:c", (2,)), EncodedEndpoint("synthetic:a", (3, 0, 7)),
            EncodedEndpoint("synthetic:b", (4, 0)))
    model = ScalarModel().eval()
    before = model.scale.detach().clone()
    scores, receipt = score_endpoints(model, rows, pad_id=0, batch_size=batch_size, device="cpu")
    assert scores == {"synthetic:a": 7.0, "synthetic:b": 0.0, "synthetic:c": 2.0}
    assert model.calls == (len(rows) + batch_size - 1) // batch_size
    assert receipt["endpoints"] == 3 and receipt["valid_tokens"] == 6
    assert receipt["padded_slots"] >= 6
    assert "synthetic:" not in json.dumps(receipt)
    assert torch.equal(model.scale.detach(), before) and model.scale.grad is None and not model.training


@pytest.mark.parametrize("case", ["training", "child_training", "duplicate", "empty", "bad_tokens", "pad", "device", "batch"])
def test_pre_forward_gate(case):
    rows = [EncodedEndpoint("synthetic:a", (1, 2))]
    model = ScalarModel().eval()
    if case == "training": model.train()
    elif case == "child_training": model.child = torch.nn.Dropout()
    elif case == "duplicate": rows += rows
    elif case == "empty": rows = []
    elif case == "bad_tokens": rows.append(EncodedEndpoint("synthetic:b", (-1,)))
    with pytest.raises(EndpointInferenceError):
        score_endpoints(model, rows, pad_id=-1 if case == "pad" else 0,
                        batch_size=0 if case == "batch" else 2, device="cuda" if case == "device" else "cpu")
    assert model.calls == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), [[1.0]], [1], "missing"])
def test_invalid_logits(value):
    class Bad(torch.nn.Module):
        def forward(self, **kwargs):
            if value == "missing": return {}
            if isinstance(value, float): return {"logits": torch.tensor([value])}
            return {"logits": torch.tensor(value)}
    with pytest.raises(EndpointInferenceError):
        score_endpoints(Bad().eval(), [EncodedEndpoint("synthetic:a", (1,))], pad_id=0, batch_size=1, device="cpu")


def matrix_fixture():
    encoded = encode_endpoints(cards(), Tokenizer(), max_len=64)
    values, _ = score_endpoints(ScalarModel().eval(), encoded, pad_id=0, batch_size=2, device="cpu")
    # Schema fixture only: duplicating values is NOT a 15-checkpoint result.
    return list(values), {key: dict(values) for key in SCORE_KEYS}


@pytest.mark.parametrize("case", ["missing_model", "extra_model", "missing_endpoint", "extra_endpoint", "nan", "bool", "duplicate_support"])
def test_score_matrix_gate(case):
    support, by_model = matrix_fixture()
    first = sorted(SCORE_KEYS)[0]
    if case == "missing_model": by_model.pop(first)
    elif case == "extra_model": by_model["unknown"] = by_model[first]
    elif case == "missing_endpoint": by_model[first].pop(support[0])
    elif case == "extra_endpoint": by_model[first]["synthetic:extra"] = 1.0
    elif case == "nan": by_model[first][support[0]] = float("nan")
    elif case == "bool": by_model[first][support[0]] = True
    else: support += support[:1]
    with pytest.raises(EndpointInferenceError):
        assemble_score_matrix(support, by_model)


def test_forward_matrix_existing_margin_and_independent_verifier(tmp_path):
    support, by_model = matrix_fixture()
    score_rows = assemble_score_matrix(support, by_model)
    h = lambda x: hashlib.sha256(x.encode()).hexdigest()
    pairs = []
    for left, right in [(support[0], support[1]), (support[0], support[2])]:
        pairs.append({"left_endpoint_id": left, "right_endpoint_id": right,
                      "pair_sha256": h(left + "\0" + right), "task_sha256": h("task"),
                      "parent_sha256": h("parent"), "run_sha256": h("run")})
    pair_path, score_path, output = [tmp_path / name for name in ("pairs.jsonl", "scores.jsonl", "margin.jsonl")]
    write(pair_path, pairs); write(score_path, score_rows)
    margins = materialize(pair_path, score_path)
    write(output, margins)
    protocol = Path(__file__).parents[1] / "g_reuse_blinded_margin_materialization_v1.json"
    assert verify(protocol, pair_path, score_path, output)["verification_pass"]
    for pair in pairs:
        margin = next(r for r in margins if r["pair_sha256"] == pair["pair_sha256"])
        for key in SCORE_KEYS:
            assert margin["margins"][key] == by_model[key][pair["left_endpoint_id"]] - by_model[key][pair["right_endpoint_id"]]
