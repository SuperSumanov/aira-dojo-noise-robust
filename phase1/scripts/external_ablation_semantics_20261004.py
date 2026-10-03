"""CPU-only synthetic semantics check; not a reproduction of MLE-STAR scores.

Fetch an exact public example, run only audited preprocessing assignments, and
compare its nominal no-imputation treatment with a real fillna deletion control.
No real dataset, labels, predictive model, generator, or private artifact is used.
"""
import argparse
import ast
import collections
import copy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import time
import urllib.request
import warnings

COMMIT = "d33445de01d66b42cf3e5093bc0623502393864c"
SOURCE = ("https://raw.githubusercontent.com/jaehyun513/MLE-STAR/" + COMMIT
          + "/example_intermediate_outputs/ablation.py")
SOURCE_SHA = "89664d56f20e9ba22139139760ad0e89b92c13c5c7034b35caa5dfbaed4cc821"
BASE = ("categorical_features", "numerical_features", "numeric_transformer",
        "categorical_transformer", "preprocessor", "X_train_processed", "X_val_processed")
NOMINAL = ("numeric_transformer_no_imputation", "categorical_transformer_no_imputation",
           "preprocessor_no_imputation", "X_train_num_imputed", "X_train_cat_imputed",
           "X_val_num_imputed", "X_val_cat_imputed", "X_train_imputed", "X_val_imputed",
           "X_train_processed_no_imputation", "X_val_processed_no_imputation")
CALLS = {"select_dtypes", "drop", "Pipeline", "SimpleImputer", "StandardScaler",
         "OneHotEncoder", "ColumnTransformer", "fit_transform", "transform",
         "fillna", "mean", "mode", "concat"}


def selected(tree, targets):
    nodes = []
    for target in targets:
        matches = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
                   and isinstance(n.targets[0], ast.Name) and n.targets[0].id == target]
        assert matches, target
        # The original file repeats numeric_transformer for an unrelated ablation.
        nodes.append(copy.deepcopy(matches[0]))
    assert [n.lineno for n in nodes] == sorted(n.lineno for n in nodes)
    for n in ast.walk(ast.Module(body=nodes, type_ignores=[])):
        if isinstance(n, ast.Call):
            assert isinstance(n.func, (ast.Attribute, ast.Name))
            assert (n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id) in CALLS
        assert not isinstance(n, (ast.Import, ast.ImportFrom, ast.Lambda, ast.NamedExpr))
    return nodes


class DeleteFill(ast.NodeTransformer):
    def __init__(self):
        self.deleted = 0

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "fillna":
            self.deleted += 1
            return copy.deepcopy(node.func.value)
        return self.generic_visit(node)


def fixtures(np, pd):
    def make(age, planet, query_age=None, query_planet=None):
        train = pd.DataFrame({"Age": np.asarray(age, dtype=float),
                              "Spend": [0., 1., 4., 4., 2., 3.],
                              "HomePlanet": pd.Series(planet, dtype=object),
                              "Name": ["n0", "n1", "n2", "n3", "n4", "n5"]})
        query = pd.DataFrame({"Age": np.asarray(query_age if query_age is not None
                                               else [np.nan, 30., 100.], dtype=float),
                              "Spend": [1., 2., 3.],
                              "HomePlanet": pd.Series(query_planet if query_planet is not None
                                                       else ["Earth", np.nan, "Titan"], dtype=object),
                              "Name": ["q0", "q1", "q2"]})
        return train, query
    missing = [20., np.nan, 40., 50., 60., 10.]
    complete = [20., 30., 40., 50., 60., 10.]
    cats = ["Earth", "Europa", np.nan, "Earth", "Mars", "Earth"]
    cats_full = ["Earth", "Europa", "Mars", "Earth", "Mars", "Earth"]
    return [
        ("mixed_missing", True, True, *make(missing, cats)),
        ("numeric_only_missing", True, True, *make(missing, cats_full,
                                                  query_planet=["Earth", "Mars", "Titan"])),
        ("categorical_only_missing", True, True, *make(complete, cats, [25., 30., 100.])),
        ("no_missing_negative_control", True, False,
         *make(complete, cats_full, [25., 30., 100.], ["Earth", "Mars", "Titan"])),
        ("tied_categorical_modes", True, True,
         *make(missing, ["Earth", "Europa", np.nan, "Earth", "Europa", np.nan])),
        ("all_missing_numeric_boundary", False, None, *make([np.nan] * 6, cats)),
        ("all_missing_categorical_boundary", False, None,
         *make(complete, [np.nan] * 6)),
    ]


def manual_reference(train, query, np):
    """Independent arithmetic/Counter implementation, not sklearn transformers."""
    numeric = []
    for col in ("Age", "Spend"):
        raw = list(train[col])
        present = [v for v in raw if not math.isnan(v)]
        fill = math.fsum(present) / len(present)
        values = [fill if math.isnan(v) else v for v in raw]
        center = math.fsum(values) / len(values)
        scale = math.sqrt(math.fsum((v - center) ** 2 for v in values) / len(values)) or 1.
        numeric.append([(fill if math.isnan(v) else v) - center for v in query[col]])
        numeric[-1] = [v / scale for v in numeric[-1]]
    counts = collections.Counter(v for v in train["HomePlanet"] if isinstance(v, str))
    fill = sorted(k for k, v in counts.items() if v == max(counts.values()))[0]
    categories = sorted(counts)
    return np.array([[numeric[0][i], numeric[1][i]]
                     + [float((v if isinstance(v, str) else fill) == cat) for cat in categories]
                     for i, v in enumerate(query["HomePlanet"])])


def same(a, b, np):
    return a.shape == b.shape and bool(np.array_equal(a, b, equal_nan=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "create-exclusive output already exists"
    started = time.time()
    expected_versions = {"numpy": "2.2.4", "pandas": "2.2.3", "scikit-learn": "1.6.1", "scipy": "1.15.2"}
    assert {p: importlib.metadata.version(p) for p in expected_versions} == expected_versions
    raw = urllib.request.urlopen(SOURCE, timeout=30).read()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA, "public source drift"
    tree = ast.parse(raw.decode("utf-8"))
    base, nominal = selected(tree, BASE), selected(tree, NOMINAL)
    deletion = DeleteFill()
    control = [deletion.visit(copy.deepcopy(n)) for n in nominal]
    assert deletion.deleted == 4
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    imports = dict(pd=pd, Pipeline=Pipeline, SimpleImputer=SimpleImputer,
                   StandardScaler=StandardScaler, OneHotEncoder=OneHotEncoder,
                   ColumnTransformer=ColumnTransformer)
    rows, manual_errors = [], []
    for name, ordinary, expect_change, train, query in fixtures(np, pd):
        outputs, descriptions = {}, {}
        for arm, nodes in (("base", base), ("nominal_no_imputation", base[:2] + nominal),
                           ("actual_fillna_deletion", base[:2] + control)):
            env = dict(imports, X=pd.concat([train, query], ignore_index=True),
                       X_train=train.copy(deep=True), X_val=query.copy(deep=True), __builtins__={})
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    module = ast.fix_missing_locations(ast.Module(body=copy.deepcopy(nodes), type_ignores=[]))
                    exec(compile(module, "<pinned-preprocessing-only>", "exec"), env)
                    suffix = "" if arm == "base" else "_no_imputation"
                    arrays = [env["X_" + role + "_processed" + suffix] for role in ("train", "val")]
                    arrays = [x.toarray() if hasattr(x, "toarray") else np.asarray(x) for x in arrays]
                    outputs[arm] = arrays
                    descriptions[arm] = {"status": "returned", "shapes": [list(x.shape) for x in arrays],
                                         "nan_counts": [int(np.isnan(x).sum()) for x in arrays]}
                    if ordinary and arm != "actual_fillna_deletion":
                        for x, frame in zip(arrays, (train, query)):
                            ref = manual_reference(train, frame, np)
                            assert ref.shape == x.shape
                            error = float(np.max(np.abs(x - ref)))
                            manual_errors.append(error)
                            assert error <= 1e-12
                except Exception as exc:
                    if ordinary:
                        raise
                    descriptions[arm] = {"status": "error", "error_type": type(exc).__name__}
                descriptions[arm]["warning_count"] = len(caught)
        nominal_equal = (all(same(a, b, np) for a, b in zip(outputs["base"], outputs["nominal_no_imputation"]))
                         if "base" in outputs and "nominal_no_imputation" in outputs else None)
        real_equal = (all(same(a, b, np) for a, b in zip(outputs["base"], outputs["actual_fillna_deletion"]))
                      if "base" in outputs and "actual_fillna_deletion" in outputs else None)
        if ordinary:
            assert nominal_equal is True
            assert real_equal is (not expect_change)
        rows.append(dict(fixture=name, ordinary_case=ordinary, base_vs_nominal_exact_equal=nominal_equal,
                         base_vs_real_deletion_exact_equal=real_equal, arms=descriptions))
    result = dict(schema="public-example-imputation-semantics-v1", source_url=SOURCE,
                  source_commit=COMMIT, source_sha256=SOURCE_SHA,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  test_definition="Five ordinary fixtures, true-deletion positive controls, no-missing negative control; two all-missing boundaries reported without equivalence assumptions.",
                  fixtures=rows, extracted_assignments={"base": len(base), "nominal": len(nominal)},
                  manual_reference_matrix_checks=len(manual_errors), maximum_manual_error=max(manual_errors),
                  actual_control_fillna_deletions=deletion.deleted,
                  python=platform.python_version(),
                  dependencies={p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn", "scipy")},
                  elapsed_seconds=time.time()-started, predictive_model_fits=0, real_data_rows=0,
                  gpu_hours=0, generator_calls=0, status="PASS",
                  boundaries=["Synthetic preprocessing semantics only; not MLE-STAR benchmark reproduction.",
                              "One published example does not establish production prevalence or score impact.",
                              "All-missing boundaries preclude universal equivalence of the two implementations.",
                              "No new search-quality improvement, new method, or agent expansion gate."])
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "fixtures": len(rows),
                      "ordinary_exact_equal": sum(r["ordinary_case"] and r["base_vs_nominal_exact_equal"] for r in rows),
                      "manual_matrix_checks": len(manual_errors), "max_manual_error": max(manual_errors),
                      "seconds": result["elapsed_seconds"],
                      "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
