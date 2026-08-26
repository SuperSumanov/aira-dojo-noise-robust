from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from phase1 import audit_historical_train_future_fuzzy_overlap as lexical_core
from phase1 import audit_historical_train_future_identifier_erased_overlap as producer
from phase1 import historical_train_future_identifier_erased_schema as schema
from phase1 import verify_historical_train_future_identifier_erased_overlap as verifier


ALPHA_A = """
def fit_pipeline(data_frame, target_column="sale_price"):
    clean_frame = data_frame.copy()
    clean_frame[target_column] = clean_frame[target_column].fillna(17)
    feature_frame = clean_frame.drop(columns=[target_column])
    target_values = clean_frame[target_column]
    fold_scores = []
    for fold_index in range(5):
        train_mask = feature_frame.index % 5 != fold_index
        valid_mask = feature_frame.index % 5 == fold_index
        model = build_model(max_depth=7, random_state=42 + fold_index)
        model.fit(feature_frame[train_mask], target_values[train_mask])
        predictions = model.predict(feature_frame[valid_mask])
        fold_scores.append(metric(target_values[valid_mask], predictions))
    return sum(fold_scores) / len(fold_scores)
"""

ALPHA_B = """
def renamed_executor(table_blob, answer_key="completely_different"):
    working_copy = table_blob.copy()
    working_copy[answer_key] = working_copy[answer_key].fillna(999)
    predictors = working_copy.drop(columns=[answer_key])
    response = working_copy[answer_key]
    measurements = []
    for rotation in range(23):
        left_side = predictors.index % 23 != rotation
        right_side = predictors.index % 23 == rotation
        estimator = alien_factory(max_depth=101, random_state=88 + rotation)
        estimator.fit(predictors[left_side], response[left_side])
        guesses = estimator.predict(predictors[right_side])
        measurements.append(other_loss(response[right_side], guesses))
    return sum(measurements) / len(measurements)
"""

UNRELATED = """
class ResourceManager:
    def __enter__(self):
        try:
            self.handle = open("resource.bin", "rb")
        except OSError as error:
            raise RuntimeError("cannot open") from error
        return self.handle

    def __exit__(self, exception_type, exception, traceback):
        if exception is not None:
            self.handle.close()
            return False
        while self.handle.read(4096):
            pass
        self.handle.close()
        return True
"""


def _jaccard(left: frozenset[int], right: frozenset[int]) -> float:
    return len(left & right) / len(left | right)


def test_schema_freezes_original_population_and_thresholds() -> None:
    producer.require_dependency_contract()
    verifier.require_dependency_contract()
    assert schema.FROZEN_COHORT_RUN_TARGET == 960
    assert schema.HISTORICAL_UNION_ENDPOINTS == 5519
    assert schema.SHINGLE_SIZE == 5
    assert (schema.PRIMARY_NUMERATOR, schema.PRIMARY_DENOMINATOR) == (17, 20)
    assert (schema.STRICT_NUMERATOR, schema.STRICT_DENOMINATOR) == (19, 20)
    assert schema.SELF_CHECK_PER_SIDE == 256


def test_alpha_renaming_and_literal_changes_are_invariant() -> None:
    left = producer.identifier_erased_tokens(ALPHA_A)
    right = producer.identifier_erased_tokens(ALPHA_B)
    assert left is not None and right is not None
    assert left == right
    assert "def" in left and "for" in left and "return" in left
    assert schema.IDENTIFIER_TOKEN in left
    assert schema.NUMBER_TOKEN in left
    assert schema.STRING_TOKEN in left


def test_producer_and_independent_tokenizers_agree_on_adversarial_fixtures() -> None:
    fixtures = [ALPHA_A, ALPHA_B, UNRELATED, "x = 1  # comment\ny = x + 2\n"]
    for code in fixtures:
        assert producer.identifier_erased_tokens(
            code
        ) == verifier.independent_identifier_erased_tokens(code)


def test_alpha_renaming_positive_control_passes_primary_and_strict() -> None:
    left_tokens = producer.identifier_erased_tokens(ALPHA_A)
    right_tokens = producer.identifier_erased_tokens(ALPHA_B)
    assert left_tokens is not None and right_tokens is not None
    left = producer.shingles_from_tokens(left_tokens)
    right = producer.shingles_from_tokens(right_tokens)
    assert left is not None and right is not None
    assert left == right
    assert _jaccard(left, right) == 1.0


def test_unrelated_negative_control_stays_below_primary_threshold() -> None:
    left_tokens = producer.identifier_erased_tokens(ALPHA_A)
    right_tokens = producer.identifier_erased_tokens(UNRELATED)
    assert left_tokens is not None and right_tokens is not None
    left = producer.shingles_from_tokens(left_tokens)
    right = producer.shingles_from_tokens(right_tokens)
    assert left is not None and right is not None
    assert 20 * len(left & right) < 17 * len(left | right)


def test_producer_and_independent_shinglers_are_byte_equivalent() -> None:
    for code in (ALPHA_A, ALPHA_B, UNRELATED):
        tokens = producer.identifier_erased_tokens(code)
        independent_tokens = verifier.independent_identifier_erased_tokens(code)
        assert tokens is not None and independent_tokens is not None
        assert producer.shingles_from_tokens(tokens) == verifier.independent_shingles(
            independent_tokens
        )


def test_tokenization_failure_and_low_shingle_support_are_distinct() -> None:
    assert producer.identifier_erased_tokens('value = """unterminated') is None
    short = producer.identifier_erased_tokens("value = 1")
    assert short is not None
    assert producer.shingles_from_tokens(short) is None


def test_prefix_join_matches_bruteforce_on_identifier_erased_controls() -> None:
    historical = []
    prospective = []
    for index, code in enumerate((ALPHA_A, UNRELATED)):
        tokens = producer.identifier_erased_tokens(code)
        assert tokens is not None
        shingles = producer.shingles_from_tokens(tokens)
        assert shingles is not None
        historical.append(lexical_core.Record(f"h{index}", f"hr{index}", "t", shingles))
    for index, code in enumerate((ALPHA_B, UNRELATED)):
        tokens = producer.identifier_erased_tokens(code)
        assert tokens is not None
        shingles = producer.shingles_from_tokens(tokens)
        assert shingles is not None
        prospective.append(lexical_core.Record(f"p{index}", f"pr{index}", "t", shingles))
    joined, candidates = lexical_core.bipartite_join(historical, prospective)
    brute = lexical_core.brute_force(historical, prospective)
    assert candidates >= len(joined)
    assert lexical_core.edge_signature(joined) == lexical_core.edge_signature(brute)
    assert {(edge.historical, edge.prospective) for edge in joined} == {(0, 0), (1, 1)}


def test_fingerprint_accounts_for_all_fixture_outcomes() -> None:
    rows = [
        lexical_core.fuzzy.CodeRecord("a", "r1", "t", "", ALPHA_A),
        lexical_core.fuzzy.CodeRecord("b", "r2", "t", "", "value = 1"),
        lexical_core.fuzzy.CodeRecord(
            "c", "r3", "t", "", 'value = """unterminated'
        ),
    ]
    values, summary = producer.fingerprint(rows)
    assert len(values) == 1
    assert summary == {
        "input_endpoints": 3,
        "fingerprinted_endpoints": 1,
        "tokenization_failures": 1,
        "too_short_or_low_distinct_shingles": 1,
        "coverage": 1 / 3,
    }


def test_hashes_are_independent_of_python_hash_seed() -> None:
    code = (
        "from phase1.audit_historical_train_future_identifier_erased_overlap "
        "import identifier_erased_tokens, shingles_from_tokens; "
        f"x={ALPHA_A!r}; print(sorted(shingles_from_tokens(identifier_erased_tokens(x))))"
    )
    outputs = []
    for seed in ("1", "999"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        outputs.append(subprocess.check_output([sys.executable, "-c", code], env=environment))
    assert outputs[0] == outputs[1]


def test_independent_verifier_does_not_import_new_producer() -> None:
    path = Path(verifier.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "phase1.audit_historical_train_future_identifier_erased_overlap" not in imported


def test_interpretation_contract_names_identifier_erased_scope() -> None:
    assert schema.PROTOCOL.endswith("identifier_erased_overlap_v1")
    assert schema.REPRESENTATION == "python_token_identifier_erased_v1"
    assert schema.MAX_PROSPECTIVE_AFFECTED_FRACTION == 0.01
    assert schema.MAX_CROSS_TASK_PROSPECTIVE_AFFECTED_FRACTION == 0.005
