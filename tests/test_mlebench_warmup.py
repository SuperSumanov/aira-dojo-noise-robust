import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from hydra import compose, initialize_config_dir
from hydra.utils import instantiate
from mlebench.registry import registry
from omegaconf import OmegaConf

from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
from dojo.config_dataclasses.task import TASK_MAP
from dojo.core.interpreters.base import ExecutionResult
from dojo.core.solvers.operators.analyze_warmup import analyze_warmup_op
from dojo.core.solvers.utils.journal import Node
from dojo.tasks.mlebench.task_warmup import MLEBenchTaskWarmup
from dojo.tasks.mlebench.warmup.converters import CONVERTERS
from dojo.tasks.mlebench.warmup.datasets import read_table
from dojo.tasks.mlebench.warmup.grade import WarmupGrader, append_feedback
from dojo.tasks.mlebench.warmup.prepare import inventory, prepare_warmup

CHAI = "chaii-hindi-and-tamil-question-answering"
SALT = "tgs-salt-identification-challenge"
DOGS = "dog-breed-identification"
TFQA = "tensorflow2-question-answering"


def make_prepared(root, competition_id):
    public = root / competition_id / "prepared/public"
    private = public.parent / "private"
    public.mkdir(parents=True)
    private.mkdir()
    (public / "description.md").write_text("Fixture competition")
    train_ids = [f"train{index:02d}" for index in range(12)]
    test_ids = [f"test{index:02d}" for index in range(10)]
    if competition_id == CHAI:
        train = pd.DataFrame(
            [
                dict(
                    id=identifier,
                    context=f"answer context {index}",
                    question="what?",
                    answer_text="answer context",
                    answer_start=0,
                    language="hindi" if index < 8 else "tamil",
                )
                for index, identifier in enumerate(train_ids)
            ]
        )
        train.to_csv(public / "train.csv", index=False)
        test = train.iloc[:10].copy()
        test["id"] = test_ids
        test.drop(columns=["answer_text", "answer_start"]).to_csv(public / "test.csv", index=False)
        sample = pd.DataFrame({"id": test_ids, "PredictionString": "dummy text"})
        sample.to_csv(public / "sample_submission.csv", index=False)
        sample["PredictionString"] = "answer context"
        sample.to_csv(private / "test.csv", index=False)
    elif competition_id in {SALT, DOGS}:
        suffix = ".png" if competition_id == SALT else ".jpg"
        for directory, identifiers in [
            ("train/images" if competition_id == SALT else "train", train_ids),
            ("test/images" if competition_id == SALT else "test", test_ids),
        ]:
            (public / directory).mkdir(parents=True)
            for identifier in identifiers:
                (public / directory / f"{identifier}{suffix}").write_bytes(b"fixture image")
        if competition_id == SALT:
            train = pd.DataFrame({"id": train_ids, "rle_mask": ""})
            train.to_csv(public / "train.csv", index=False)
            pd.DataFrame({"id": train_ids, "z": range(12)}).to_csv(public / "depths.csv", index=False)
            (public / "train/masks").mkdir()
            for identifier in train_ids:
                (public / "train/masks" / f"{identifier}.png").write_bytes(b"mask")
            sample = pd.DataFrame({"id": test_ids, "rle_mask": ""})
            sample.to_csv(private / "test.csv", index=False)
        else:
            module = importlib.import_module("mlebench.competitions.dog-breed-identification.prepare")
            train = pd.DataFrame({"id": train_ids, "breed": module.DOGS_LIST[:12]})
            train.to_csv(public / "labels.csv", index=False)
            answers = module.to_one_hot(pd.DataFrame({"id": test_ids, "breed": module.DOGS_LIST[:10]}))
            answers.to_csv(private / "test.csv", index=False)
            sample = answers.copy()
            sample.loc[:, sample.columns != "id"] = 1 / 120
        sample.to_csv(public / "sample_submission.csv", index=False)
    else:
        train_ids = [str(100 + index) for index in range(12)]
        test_ids = [str(200 + index) for index in range(10)]

        def record(identifier):
            return dict(
                example_id=identifier,
                question_text="where?",
                document_text="a b c",
                long_answer_candidates=[dict(start_token=0, end_token=3, top_level=True)],
                annotations=[
                    dict(
                        long_answer=dict(start_token=0, end_token=3),
                        short_answers=[dict(start_token=1, end_token=2)],
                        yes_no_answer="NONE",
                    )
                ],
            )

        for path, identifiers, labels in [
            (public / "simplified-nq-train.jsonl", train_ids, True),
            (public / "simplified-nq-test.jsonl", test_ids, False),
            (private / "test.jsonl", test_ids, True),
        ]:
            with path.open("w") as stream:
                for identifier in identifiers:
                    value = record(identifier)
                    if not labels:
                        del value["annotations"]
                    stream.write(json.dumps(value) + "\n")
        pd.DataFrame(
            [
                {"example_id": f"{identifier}_{kind}", "PredictionString": ""}
                for identifier in test_ids
                for kind in ["short", "long"]
            ]
        ).to_csv(public / "sample_submission.csv", index=False)
    return public


@pytest.fixture(params=list(CONVERTERS))
def converted(tmp_path, request):
    source = tmp_path / "data"
    public = make_prepared(source, request.param)
    before = inventory(public)
    version = tmp_path / "warmup"
    manifest = prepare_warmup(source, version, request.param)
    assert inventory(public) == before
    competition = registry.set_data_dir(source).get_competition(request.param)
    return competition, version, manifest


def test_conversion_and_original_score_preserved(converted, tmp_path):
    competition, directory, manifest = converted
    assert manifest["target_count"] == manifest["actual_count"] == 2
    grader = WarmupGrader(competition, directory)
    sample = directory / "public/sample_submission.csv"
    report, feedback, valid = grader.grade(sample, tmp_path / "results")
    assert valid
    assert feedback["status"] == "scored"
    original = pd.read_csv(competition.sample_submission, dtype={"id": str, "example_id": str})
    expected = competition.grader(original, grader.original_answers)
    assert report["score"] == expected
    shuffled = read_table(sample).sample(frac=1, random_state=5)
    shuffled.to_csv(tmp_path / "shuffled.csv", index=False)
    reordered, _, valid = grader.grade(tmp_path / "shuffled.csv", tmp_path / "results")
    assert valid and reordered["score"] == expected
    if competition.id == TFQA:
        public_records = [
            json.loads(line) for line in (directory / "public/simplified-nq-test.jsonl").read_text().splitlines()
        ]
        assert all("annotations" not in row for row in public_records)
        assert len(public_records) == 12
        assert len(read_table(sample)) == 24
    elif competition.id == SALT:
        for identifier in manifest["warmup_ids"]:
            assert not (directory / "public/train/masks" / f"{identifier}.png").exists()
        depths = read_table(directory / "public/depths.csv")
        assert not set(depths["id"]) & set(manifest["warmup_ids"])


@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate", "empty"])
def test_invalid_submission_ids(converted, tmp_path, defect):
    competition, directory, _ = converted
    grader = WarmupGrader(competition, directory)
    sample = read_table(directory / "public/sample_submission.csv")
    column = "example_id" if competition.id == TFQA else "id"
    if defect == "missing":
        sample = sample.iloc[1:]
    elif defect == "extra":
        extra = sample.iloc[:1].copy()
        extra[column] = "unexpected"
        sample = pd.concat([sample, extra])
    elif defect == "duplicate":
        sample = pd.concat([sample, sample.iloc[:1]])
    else:
        sample.loc[0, column] = ""
    sample.to_csv(tmp_path / "bad.csv", index=False)
    _, feedback, valid = grader.grade(tmp_path / "bad.csv", tmp_path / "results")
    assert not valid
    assert feedback["status"] == "invalid_submission"
    assert "score" in feedback and feedback["score"] is None
    report = json.loads((tmp_path / "results/grading_report.json").read_text())
    assert report["valid_submission"] is False
    assert report["score"] is None


def test_malformed_predictions_write_invalid_reports(converted, tmp_path):
    competition, directory, _ = converted
    grader = WarmupGrader(competition, directory)
    submission = read_table(directory / "public/sample_submission.csv")
    if competition.id == CHAI:
        submission = submission.drop(columns="PredictionString")
    elif competition.id == SALT:
        submission["rle_mask"] = "not integers"
    elif competition.id == DOGS:
        submission[submission.columns[1]] = "invalid probability"
    else:
        submission["PredictionString"] = "bad:span"
    path = tmp_path / "bad.csv"
    submission.to_csv(path, index=False)
    report, feedback, valid = grader.grade(path, tmp_path / "results")
    assert not valid
    assert report["valid_submission"] is False
    assert feedback["status"] == "invalid_submission"


def test_grade_part_uses_upstream_wrapper_and_copies_inputs(converted, monkeypatch):
    competition, directory, _ = converted
    grader = WarmupGrader(competition, directory)
    submission = pd.DataFrame({"prediction": ["unchanged"]})
    answers = {"labels": ["unchanged"]}
    calls = []

    class UpstreamGrader:
        def __call__(self, predictions, labels):
            calls.append(True)
            predictions.loc[0, "prediction"] = "changed"
            labels["labels"][0] = "changed"
            return 0.12346

    monkeypatch.setattr(grader, "competition", SimpleNamespace(grader=UpstreamGrader()))
    assert grader.grade_part(submission, answers) == 0.12346
    assert calls == [True]
    assert submission.loc[0, "prediction"] == "unchanged"
    assert answers == {"labels": ["unchanged"]}


def test_upstream_grader_exception_becomes_failed_score(converted, monkeypatch, caplog):
    competition, directory, _ = converted
    grader = WarmupGrader(competition, directory)

    def broken_grade(submission, answers):
        raise RuntimeError("grader implementation error")

    monkeypatch.setattr(competition.grader, "grade_fn", broken_grade)
    assert grader.grade_part(pd.DataFrame(), {}) is None
    assert "grader implementation error" in caplog.text


@pytest.mark.parametrize("score", [None, float("nan"), float("inf"), -float("inf")])
def test_failed_or_nonfinite_scores_are_not_reported_as_valid(converted, monkeypatch, score):
    competition, directory, _ = converted
    grader = WarmupGrader(competition, directory)
    monkeypatch.setattr(grader, "competition", SimpleNamespace(grader=lambda submission, answers: score))
    assert grader.grade_part(pd.DataFrame(), {}) is None


def test_unreadable_csv_replaces_old_report(converted, tmp_path):
    competition, directory, _ = converted
    grader = WarmupGrader(competition, directory)
    results = tmp_path / "results"
    grader.grade(directory / "public/sample_submission.csv", results)
    path = tmp_path / "empty.csv"
    path.write_text("")
    report, feedback, valid = grader.grade(path, results)
    assert not valid and report["score"] is None
    assert feedback["error"] == "missing_id_column"
    assert json.loads((results / "grading_report.json").read_text())["score"] is None


@pytest.mark.parametrize("defect", ["missing_half", "unexpected_suffix"])
def test_tensorflow_preparation_requires_complete_submission_pairs(tmp_path, defect):
    source = tmp_path / "data"
    public = make_prepared(source, TFQA)
    sample = read_table(public / "sample_submission.csv")
    if defect == "missing_half":
        sample = sample.iloc[1:]
    else:
        sample.loc[0, "example_id"] = "200_other"
    sample.to_csv(public / "sample_submission.csv", index=False)
    with pytest.raises(ValueError, match="short/long pairs"):
        prepare_warmup(source, tmp_path / "warmup", TFQA)


def test_analysis_has_feedback_before_first_call_and_after_long_logs():
    node = Node(code="print('CV: 0.91')")
    output = ExecutionResult(["x" * 100_000 + "\nCV: 0.91"], 1.0, 0)
    feedback = dict(
        status="scored",
        score=0.12,
        metric="Jaccard",
        lower_is_better=False,
        num_samples=23,
        num_submission_rows=23,
        version="fixture",
    )
    append_feedback(output, feedback)
    node.absorb_exec_result(output)
    captured = {}

    def analyze_llm(**kwargs):
        captured.update(kwargs)
        return {"metric": 0.91, "summary": "check inference", "is_bug": False}, {}

    response, _ = analyze_warmup_op(analyze_llm, None, "task", node)
    assert response["metric"] == 0.91
    assert json.loads(captured["query_data"]["warmup_feedback"]) == feedback
    assert '"score": 0.12' in captured["query_data"]["execution_output"]
    assert "CV metric" in captured["json_schema"]


@pytest.mark.parametrize("solver_name", ["warmup_greedy", "warmup_mcts"])
def test_new_task_and_operator_config_compose(solver_name):
    register_new_resolvers()
    with initialize_config_dir(config_dir=str(Path("src/dojo/configs").resolve()), version_base=None):
        config = compose(
            config_name="default_run",
            overrides=[
                "task=mlebench_warmup",
                f"solver=mlebench/{solver_name}",
                "interpreter=python",
                f"task.name={CHAI}",
                "task.warmup_dir=/tmp/warmup-test",
                "task.cache_dir=/tmp/source",
            ],
        )
        task_config = instantiate(config.task)
        assert type(task_config).__name__ == "MLEBenchTaskWarmupConfig"
        assert type(instantiate(config.solver.operators.analyze)).__name__ == "WarmupAnalyzeOperatorConfig"
        solver_config = instantiate(config.solver)
        assert type(solver_config.operators["analyze"]).__name__ == "WarmupAnalyzeOperatorConfig"
        assert "MLEBenchTaskWarmupConfig" in TASK_MAP
        assert config.solver.use_test_score is False


def test_warmup_batch_config_expansion_and_serialization(tmp_path):
    from dojo.config_dataclasses.benchmark import BenchmarkConfig
    from dojo.config_dataclasses.operators.analyze_warmup import WarmupAnalyzeOperatorConfig
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.task.mlebench import MLEBenchTaskConfig
    from dojo.config_dataclasses.task.mlebench_warmup import MLEBenchTaskWarmupConfig

    register_new_resolvers()
    with initialize_config_dir(config_dir=str(Path("src/dojo/configs").resolve()), version_base=None):
        config = compose(
            config_name="default_runner",
            overrides=[
                "+_exp=mlebench/aira_mcts_qwen_medium_lora",
                "benchmark=mlebench/warmup",
                f"benchmark.warmup_root={tmp_path}",
                f"benchmark.tasks=[{CHAI},{DOGS}]",
                "solver=mlebench/warmup_mcts",
                *[
                    f"solver/client@solver.operators.{operator}.llm.client=litellm_qwen3.8-27b"
                    for operator in ["analyze", "debug", "draft", "improve"]
                ],
                "launcher=srun_pool",
                "launcher.debug=true",
                "logger.use_wandb=false",
            ],
        )
        runner = instantiate(config)
    assert list(runner.vars["metadata.seed"]) == list(range(1, 9))
    assert runner.solver.use_test_score is False
    tasks = runner.benchmark.to_cfg_list()
    assert len(tasks) == 2
    for task in tasks:
        assert isinstance(task, MLEBenchTaskWarmupConfig)
        assert task.warmup_dir == str(tmp_path / task.name / "v1")
        run = RunConfig(
            id="batch-test",
            task=task,
            solver=runner.solver,
            interpreter=runner.interpreter,
            logger=runner.logger,
            metadata=runner.metadata,
        )
        resolved = OmegaConf.structured(run)
        OmegaConf.resolve(resolved)
        run = OmegaConf.to_object(resolved)
        run.validate()
        assert run.task.public_dir == str(tmp_path / task.name / "v1/public")
        assert run.task.data_dir == run.task.public_dir
        restored = RunConfig.from_dict(run.to_typed_dict())
        assert isinstance(restored.task, MLEBenchTaskWarmupConfig)
        assert isinstance(restored.solver.operators["analyze"], WarmupAnalyzeOperatorConfig)
        assert restored.solver.operators["analyze"].llm.generation_kwargs["reasoning_effort"] == "medium"
    runner.benchmark.overrides = {"cache_dir": "/source"}
    runner.benchmark.task_overrides = {CHAI: {"cache_dir": "/chaii-source", "warmup_dir": "/custom/chaii"}}
    tasks = runner.benchmark.to_cfg_list()
    assert tasks[0].cache_dir == "/chaii-source" and tasks[0].warmup_dir == "/custom/chaii"
    assert tasks[1].cache_dir == "/source"
    original = BenchmarkConfig(name="mlebench", tasks=[CHAI]).to_cfg_list()
    assert type(original[0]) is MLEBenchTaskConfig


@pytest.mark.parametrize(
    "module_name,class_name",
    [
        ("dojo.solvers.greedy.greedy", "Greedy"),
        ("dojo.solvers.mcts.mcts", "MCTS"),
        ("dojo.solvers.evo.evo", "Evolutionary"),
        ("dojo.solvers.blind_ts.blind_ts", "BlindTS"),
        ("dojo.solvers.fore_ts.fore_ts", "ForeTS"),
    ],
)
def test_solver_warmup_operator_wiring(monkeypatch, module_name, class_name):
    from dojo.config_dataclasses.operators.analyze_warmup import WarmupAnalyzeOperatorConfig
    from dojo.config_dataclasses.operators.base import OperatorConfig

    module = importlib.import_module(module_name)
    solver_class = getattr(module, class_name)
    setup_module = importlib.import_module(solver_class.setup_operators.__module__)
    monkeypatch.setattr(setup_module, "GenericLLM", lambda config: config)
    monkeypatch.setattr(setup_module, "create_memory_op", lambda config: None)
    solver = solver_class.__new__(solver_class)
    solver.cfg = SimpleNamespace(
        operators={name: OperatorConfig() for name in ["draft", "improve", "debug", "crossover"]},
        memory=None,
        debug_memory=None,
        use_test_score=False,
    )
    solver.cfg.operators["analyze"] = WarmupAnalyzeOperatorConfig()
    solver.task_info = {"warmup": True}
    solver.setup_operators()
    assert solver.analyze_fn.func is analyze_warmup_op

    async def analyze(task_description, node):
        return {"metric": 0.91, "summary": "warmup pipeline checked", "is_bug": False}, {}

    solver.analyze_fn = analyze
    solver.task_desc = "fixture task"
    solver.state = SimpleNamespace(current_step=1)
    solver.logger = SimpleNamespace(info=lambda *args: None)
    assert solver._analyze(Node(code="print('CV: 0.91')"))["metric"] == 0.91
    solver.cfg.use_test_score = True
    with pytest.raises(ValueError, match="use_test_score=false"):
        solver.setup_operators()
    solver.cfg.use_test_score = False
    solver.task_info = {}
    with pytest.raises(ValueError, match="enabled together"):
        solver.setup_operators()
    solver.cfg.operators["analyze"] = OperatorConfig()
    solver.setup_operators()
    assert solver.analyze_fn.func is not analyze_warmup_op


def test_greedy_selection_keeps_cv_and_passes_analysis_to_memory():
    from dojo.solvers.greedy.greedy import Greedy
    from dojo.core.solvers.operators.memory import get_node_summary
    from dojo.config_dataclasses.operators.analyze_warmup import WarmupAnalyzeOperatorConfig

    solver = Greedy.__new__(Greedy)
    solver.cfg = SimpleNamespace(operators={"analyze": WarmupAnalyzeOperatorConfig()}, use_test_score=False)
    solver.task_desc = "fixture"
    solver.state = SimpleNamespace(current_step=1)
    solver.lower_is_better = False
    solver.logger = SimpleNamespace(**{level: lambda *args: None for level in ["info", "debug", "warning", "error"]})

    async def analyze(task_description, node):
        feedback = json.loads(node._term_out[-1].split("[Harness warmup grading]\n")[1])
        assert feedback["score"] == 0.12
        return {"metric": 0.91, "summary": "Check inference alignment: CV 0.91, warmup 0.12.", "is_bug": False}, {}

    solver.analyze_fn = analyze
    output = ExecutionResult(["CV: 0.91"], 1.0, 0)
    append_feedback(output, {"status": "scored", "score": 0.12})
    node = Node(code="print('CV: 0.91')", plan="fixture plan")
    solver.parse_eval_result(
        node,
        {
            "execution_output": output,
            "valid_solution": True,
            "aux_eval_info": {"score": 0.00017, "gold_threshold": 0.99999},
        },
    )
    assert node.metric.value == 0.91
    summary = get_node_summary(node)
    assert "warmup 0.12" in summary
    assert "0.00017" not in summary and "0.99999" not in summary


def test_typed_config_roundtrip_keeps_warmup_types():
    from dojo.config_dataclasses.operators.analyze_warmup import WarmupAnalyzeOperatorConfig
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.solver.greedy import GreedySolverConfig
    from dojo.config_dataclasses.task.mlebench_warmup import MLEBenchTaskWarmupConfig

    config = RunConfig(
        task=MLEBenchTaskWarmupConfig(name=CHAI, warmup_dir="/tmp/warmup"),
        solver=GreedySolverConfig(operators={"analyze": WarmupAnalyzeOperatorConfig()}),
    )
    restored = RunConfig.from_dict(config.to_typed_dict())
    assert isinstance(restored.task, MLEBenchTaskWarmupConfig)
    assert isinstance(restored.solver.operators["analyze"], WarmupAnalyzeOperatorConfig)


def test_perfect_answers_have_expected_scores(converted, tmp_path):
    competition, directory, _ = converted
    grader = WarmupGrader(competition, directory)
    if competition.id == TFQA:
        records = []
        for answer in grader.original_answers + grader.warmup_answers:
            annotation = answer["annotations"][0]
            for kind in ["short", "long"]:
                span = annotation["long_answer"] if kind == "long" else annotation["short_answers"][0]
                records.append(
                    {
                        "example_id": f"{answer['example_id']}_{kind}",
                        "PredictionString": f"{span['start_token']}:{span['end_token']}",
                    }
                )
        submission = pd.DataFrame(records)
    else:
        submission = pd.concat([grader.original_answers, grader.warmup_answers])
    path = tmp_path / "perfect.csv"
    submission.to_csv(path, index=False)
    report, feedback, valid = grader.grade(path, tmp_path / "results")
    assert valid
    expected = 0.0 if competition.id == DOGS else 1.0
    assert report["score"] == feedback["score"] == expected


def test_task_step_and_final_grading(tmp_path):
    data = tmp_path / "data"
    make_prepared(data, CHAI)
    directory = tmp_path / "warmup"
    prepare_warmup(data, directory, CHAI)
    from dojo.config_dataclasses.task.mlebench_warmup import MLEBenchTaskWarmupConfig

    cfg = MLEBenchTaskWarmupConfig(
        name=CHAI,
        cache_dir=str(data),
        warmup_dir=str(directory),
        public_dir=str(directory / "public"),
        data_dir=str(directory / "public"),
        private_dir=str(data / CHAI / "prepared/private"),
        results_output_dir=str(tmp_path / "results"),
    )
    task = MLEBenchTaskWarmup(cfg)

    class Interpreter:
        working_dir = tmp_path / "workspace"
        factory = False

        def run(self, solution, file_name):
            sample = read_table(directory / "public/sample_submission.csv")
            sample.to_csv(self.working_dir / "submission.csv", index=False)
            return ExecutionResult(["CV: 0.91"], 1.0, 0)

        def fetch_file(self, path):
            return None

    interpreter = Interpreter()
    interpreter.working_dir.mkdir()
    state, info = task.prepare(solver_interpreter=interpreter)
    assert info["warmup"]
    _, result = task.step_task(state, "print('hello')")
    assert result["valid_solution"]
    assert "Harness warmup grading" in result["execution_output"].term_out[-1]
    assert not (interpreter.working_dir / "submission.csv").exists()
    final = task.evaluate_fitness(solution="print('hello')", interpreter=interpreter)
    assert final["test_fitness"] == result["test_fitness"]


def test_version_is_reproducible_and_not_overwritten(tmp_path):
    source = tmp_path / "data"
    make_prepared(source, CHAI)
    first = prepare_warmup(source, tmp_path / "first", CHAI)
    second = prepare_warmup(source, tmp_path / "second", CHAI)
    assert first == second
    with pytest.raises(FileExistsError):
        prepare_warmup(source, tmp_path / "first", CHAI)
