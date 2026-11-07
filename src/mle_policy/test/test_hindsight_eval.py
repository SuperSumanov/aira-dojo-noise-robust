"""Tests for manifests and measured-result reporting."""

import json
import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.mle_policy.src.data.hindsight.exp import evaluate as evaluation
from src.mle_policy.src.data.hindsight.exp.prepare import prepare
from src.mle_policy.src.data.hindsight.exp.summarize import summarize


@pytest.fixture
def experiment(tmp_path):
    source = tmp_path / "journal.jsonl"
    nodes = [
        {"step": 0, "id": "context", "parents": [], "operators_used": [], "operators_metrics": []},
        {
            "step": 1,
            "id": "proposal",
            "parents": [0],
            "operators_used": ["draft"],
            "operators_metrics": [{}],
            "code": "raise ValueError()",
            "plan": "Original",
            "is_buggy": True,
        },
        {
            "step": 2,
            "id": "fixed",
            "parents": [1],
            "operators_used": ["debug"],
            "operators_metrics": [{}],
            "code": "print(42)",
            "is_buggy": False,
            "metric": 0.9,
            "metric_info/score": 0.8,
            "exec_time": 20,
        },
    ]
    source.write_text("\n".join(json.dumps({"data": node}) for node in nodes))
    (tmp_path / "source.json").write_text(json.dumps({"journal": str(source), "config": "config.json"}))
    generation = tmp_path / "generation" / "debug-1-1-hint-only"
    generation.mkdir(parents=True)
    (generation / "diagnostics.json").write_text(json.dumps({"case": "debug:1:1", "include_code": False}))
    (generation / "nodes.json").write_text(json.dumps([{"code": "print(43)", "plan": "New plan", "metric": 0.9}]))
    return tmp_path


def test_prepare_preserves_controls(experiment):
    prepare(experiment)
    manifest = json.loads((experiment / "manifest.json").read_text())
    assert len(manifest["runs"]) == 3
    assert (experiment / "runs/original-1/attempt-0.py").read_text() == "raise ValueError()"
    assert (experiment / "runs/terminal-reference-1/attempt-0.py").read_text() == "print(42)"
    record = manifest["runs"][0]
    assert record["historical_debug_calls"] == 1
    assert record["historical_steps"] == [1, 2]
    assert record["historical_cv"] == 0.9
    assert record["historical_test"] == 0.8


def test_prepare_refuses_to_replace_existing_code(experiment):
    prepare(experiment)
    (experiment / "runs/original-1/attempt-0.py").write_text("different code")
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        prepare(experiment)


def test_inherited_metric_is_not_measured_success(experiment):
    prepare(experiment)
    summarize(experiment)
    rows = json.loads((experiment / "results.json").read_text())
    assert all(row["test_score"] is None for row in rows)
    assert all(row["debug_calls_to_success"] is None for row in rows)
    assert all(not row["resolved"] for row in rows)
    assert all(row["status"] == "not_run" for row in rows)


def test_report_counts_repairs_until_success(experiment):
    prepare(experiment)
    directory = experiment / "runs/debug-1-1-hint-only"
    for attempt, valid in enumerate((False, True)):
        (directory / f"attempt-{attempt}.json").write_text(
            json.dumps(
                {
                    "attempt": attempt,
                    "valid": valid,
                    "test_score": 0.7 if valid else None,
                    "execution": {"exec_time": 10},
                }
            )
        )
    summarize(experiment)
    row = json.loads((experiment / "results.json").read_text())[0]
    assert row["debug_calls_to_success"] == 1
    assert row["executed_attempts"] == 2
    assert row["execution_seconds"] == 20
    assert row["test_score"] == 0.7
    assert row["status"] == "resolved"
    assert row["first_attempt_valid"] is False
    assert "debug-1-1-hint-only" not in evaluation.pending_runs(experiment)


def test_failed_attempt_needs_repair_without_implying_budget_exhaustion(experiment):
    prepare(experiment)
    directory = experiment / "runs/debug-1-1-hint-only"
    (directory / "attempt-0.json").write_text(
        json.dumps(
            {
                "attempt": 0,
                "valid": False,
                "test_score": None,
                "execution": {"exec_time": 10},
            }
        )
    )
    summarize(experiment)
    row = json.loads((experiment / "results.json").read_text())[0]
    assert row["status"] == "needs_repair"
    assert row["debug_calls_to_success"] is None
    (directory / "attempt-1.py").write_text("print(44)")
    summarize(experiment)
    row = json.loads((experiment / "results.json").read_text())[0]
    assert row["status"] == "repair_ready"
    assert "debug-1-1-hint-only" in evaluation.pending_runs(experiment)


@pytest.fixture
def chain(experiment, monkeypatch):
    prepare(experiment)
    args = SimpleNamespace(
        output=experiment,
        name="debug-1-1-hint-only",
        timeout=7200,
        cpus_per_task=8,
        base_url="http://model:8000/v1",
    )
    events = []
    outcomes = [False, True]

    def execute_attempt(args):
        directory = args.output / "runs" / args.name
        path = directory / f"attempt-{args.attempt}.json"
        if path.exists():
            return json.loads(path.read_text())
        assert (directory / f"attempt-{args.attempt}.py").exists()
        events.append(("execute", args.attempt))
        valid = outcomes[args.attempt]
        result = {
            "attempt": args.attempt,
            "valid": valid,
            "test_score": 0.7 if valid else None,
            "execution": {"exec_time": 10},
        }
        path.write_text(json.dumps(result))
        return result

    def repair(args):
        path = args.output / "runs" / args.name / f"attempt-{args.attempt + 1}.py"
        if not path.exists():
            events.append(("repair", args.attempt))
            path.write_text("print(44)")

    monkeypatch.setattr(evaluation, "execute_attempt", execute_attempt)
    monkeypatch.setattr(evaluation, "repair", repair)
    return args, events, outcomes


def test_chain_executes_repairs_and_stops_at_success(chain):
    args, events, outcomes = chain
    assert evaluation.evaluate_chain(args) is True
    assert events == [("execute", 0), ("repair", 0), ("execute", 1)]
    summarize(args.output)
    row = json.loads((args.output / "results.json").read_text())[0]
    assert row["test_score"] == 0.7
    assert row["debug_calls_to_success"] == 1
    events.clear()
    assert evaluation.evaluate_chain(args) is True
    assert events == []


def test_successful_first_execution_needs_no_model(chain):
    args, events, outcomes = chain
    outcomes[0] = True
    assert evaluation.evaluate_chain(args) is True
    assert events == [("execute", 0)]


def test_resume_executes_existing_repair_without_regenerating(chain):
    args, events, outcomes = chain
    directory = args.output / "runs" / args.name
    args.attempt = 0
    evaluation.execute_attempt(args)
    (directory / "attempt-1.py").write_text("existing repair")
    events.clear()
    assert evaluation.evaluate_chain(args) is True
    assert events == [("execute", 1)]
    assert (directory / "attempt-1.py").read_text() == "existing repair"


def test_failed_attempt_is_pending_even_before_repair_is_generated(chain):
    args, events, outcomes = chain
    args.attempt = 0
    evaluation.execute_attempt(args)
    assert args.name in evaluation.pending_runs(args.output)


def test_four_failed_repairs_end_chain_without_claiming_success(chain):
    args, events, outcomes = chain
    outcomes[:] = [False] * 5
    assert evaluation.evaluate_chain(args) is False
    assert [attempt for event, attempt in events if event == "execute"] == list(range(5))
    assert [attempt for event, attempt in events if event == "repair"] == list(range(4))
    assert args.name not in evaluation.pending_runs(args.output)
    summarize(args.output)
    row = json.loads((args.output / "results.json").read_text())[0]
    assert row["status"] == "repair_budget_exhausted"
    assert row["resolved"] is False
    assert row["test_score"] is None
    assert row["debug_calls_to_success"] is None


@pytest.mark.parametrize("variant", ["terminal-reference", "donor-reference"])
def test_failed_controls_are_reported_without_modifying_baseline(chain, variant):
    args, events, outcomes = chain
    directory = args.output / "runs" / args.name
    metadata = json.loads((directory / "metadata.json").read_text())
    metadata["variant"] = variant
    (directory / "metadata.json").write_text(json.dumps(metadata))
    manifest = json.loads((args.output / "manifest.json").read_text())
    manifest["runs"][0]["variant"] = variant
    (args.output / "manifest.json").write_text(json.dumps(manifest))
    assert evaluation.evaluate_chain(args) is False
    assert events == [("execute", 0)]
    assert args.name not in evaluation.pending_runs(args.output)
    summarize(args.output)
    assert json.loads((args.output / "results.json").read_text())[0]["status"] == "reference_failed"


def test_infrastructure_failure_does_not_generate_code_repair(chain, monkeypatch):
    args, events, outcomes = chain

    def failed_execution(args):
        raise RuntimeError("Jupyter kernel readiness failure")

    monkeypatch.setattr(evaluation, "execute_attempt", failed_execution)
    with pytest.raises(RuntimeError, match="readiness"):
        evaluation.evaluate_chain(args)
    assert events == []
    assert not (args.output / "runs" / args.name / "attempt-0.json").exists()


def test_prepare_adds_improve_controls_without_seed_specific_logic(experiment):
    source = experiment / "journal.jsonl"
    nodes = [json.loads(line)["data"] for line in source.read_text().splitlines()]
    nodes.append(
        {**nodes[-1], "step": 3, "id": "donor", "parents": [2], "operators_used": ["improve"], "code": "print(45)"}
    )
    source.write_text("\n".join(json.dumps({"data": node}) for node in nodes))
    generation = experiment / "generation/debug-1-1-hint-only"
    generation.rename(experiment / "generation/improve-1-1-hint-only")
    generation = experiment / "generation/improve-1-1-hint-only"
    (generation / "diagnostics.json").write_text(json.dumps({"case": "improve:1:3", "include_code": False}))
    prepare(experiment)
    records = json.loads((experiment / "manifest.json").read_text())["runs"]
    assert {record["variant"] for record in records} == {"hint-only", "terminal-reference", "donor-reference"}
    donor = next(record for record in records if record["variant"] == "donor-reference")
    assert donor["source_step"] == 3
    assert (experiment / "runs" / donor["name"] / "attempt-0.py").read_text() == "print(45)"


def test_prepare_reuses_target_terminal_when_it_is_also_an_improve_donor(experiment):
    directory = experiment / "generation/debug-1-1-hint-only"
    (directory / "diagnostics.json").write_text(json.dumps({"case": "improve:1:1", "include_code": False}))
    prepare(experiment)
    records = json.loads((experiment / "manifest.json").read_text())["runs"]
    assert {record["variant"] for record in records} == {"hint-only", "terminal-reference"}


def test_batch_schedules_full_chains_for_multiple_directories(chain, monkeypatch, tmp_path):
    worker_args, events, outcomes = chain
    outcomes[:] = [True]
    other = tmp_path.parent / (tmp_path.name + "_other")
    shutil.copytree(worker_args.output, other)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        args = SimpleNamespace(**vars(worker_args))
        args.output = Path(command[command.index("--output") + 1])
        args.name = command[command.index("--name") + 1]
        return SimpleNamespace(returncode=0 if evaluation.evaluate_chain(args) else 1)

    monkeypatch.setattr(evaluation.subprocess, "run", run)
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    args = SimpleNamespace(
        output=[worker_args.output, other],
        local=False,
        workers=2,
        cpus_per_task=8,
        timeout=7200,
        base_url="http://model:8000/v1",
    )
    evaluation.evaluate(args)
    assert len(commands) == 6
    for command in commands:
        assert command[:2] == ["srun", "--jobid=123"]
        assert "--exclusive" in command and "--gres=gpu:1" in command
        assert "mle_policy.src.data.hindsight.exp.evaluate" in command
        assert command[command.index("--base-url") + 1] == args.base_url
    for directory in args.output:
        assert all(row["resolved"] for row in json.loads((directory / "results.json").read_text()))
        assert evaluation.pending_runs(directory) == []


def test_batch_failure_still_writes_summary(chain, monkeypatch):
    worker_args, events, outcomes = chain
    monkeypatch.setattr(evaluation.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    args = SimpleNamespace(
        output=[worker_args.output],
        local=True,
        workers=1,
        cpus_per_task=8,
        timeout=7200,
        base_url=None,
    )
    with pytest.raises(RuntimeError, match="failed or exhausted"):
        evaluation.evaluate(args)
    rows = json.loads((worker_args.output / "results.json").read_text())
    assert all(row["status"] == "not_run" for row in rows)


def test_local_execution_requires_serial_worker(experiment):
    with pytest.raises(ValueError, match="workers 1"):
        evaluation.evaluate(SimpleNamespace(output=[experiment], local=True, workers=2))


@pytest.fixture
def runtime(experiment, monkeypatch):
    prepare(experiment)
    config = experiment / "config.json"
    config.write_text(json.dumps({"interpreter": {}, "task": {"public_dir": str(experiment)}}))
    source = json.loads((experiment / "source.json").read_text())
    source["config"] = str(config)
    (experiment / "source.json").write_text(json.dumps(source))

    @dataclass
    class Execution:
        term_out: list
        exec_time: float = 10
        exit_code: int = 0
        timed_out: bool = False

    state = SimpleNamespace(
        execution=Execution(["done"]),
        score=0.42,
        closed=False,
        code=None,
        interpreter=None,
    )

    class Task:
        def __init__(self, config):
            pass

        def prepare(self, solver_interpreter):
            state.interpreter = solver_interpreter
            return {}, "task"

        def step_task(self, task_state, code):
            state.code = code
            return task_state, {
                "execution_output": state.execution,
                "valid_solution": True,
                "test_fitness": state.score,
            }

        def close(self, task_state):
            state.closed = True

    modules = {
        "dojo.config_dataclasses.interpreter.jupyter": {"JupyterInterpreterConfig": lambda **kwargs: kwargs},
        "dojo.core.interpreters.jupyter.jupyter_interpreter": {"JupyterInterpreter": lambda config, public: config},
        "dojo.tasks.mlebench.task": {"MLEBenchTask": Task},
    }
    for name, attributes in modules.items():
        monkeypatch.setitem(sys.modules, name, SimpleNamespace(**attributes))
    monkeypatch.setattr(evaluation.subprocess, "check_output", lambda *args, **kwargs: "0, GPU-test, test GPU")
    monkeypatch.setenv("SLURM_JOB_ID", "test")
    args = SimpleNamespace(output=experiment, name="debug-1-1-hint-only", attempt=0, timeout=7200, cpus_per_task=8)
    return args, state


def test_dojo_execution_persists_official_score_and_unchanged_code(runtime):
    args, state = runtime
    result = evaluation.execute_attempt(args)
    assert result["valid"] is True
    assert result["test_score"] == 0.42
    assert state.code == "```python\nprint(43)\n```"
    assert state.interpreter["env"]["OMP_NUM_THREADS"] == "8"
    assert state.closed is True
    assert evaluation.execute_attempt(args) == result


@pytest.mark.parametrize("score", [None, float("nan"), float("inf"), True])
def test_missing_or_nonfinite_score_does_not_resolve_chain(runtime, score):
    args, state = runtime
    state.score = score
    result = evaluation.execute_attempt(args)
    assert result["valid"] is False
    assert result["test_score"] is None


def test_real_kernel_readiness_output_is_infrastructure_failure(runtime):
    args, state = runtime
    state.execution.term_out = ["Kernel did not become ready in time."]
    with pytest.raises(RuntimeError, match="readiness"):
        evaluation.execute_attempt(args)
    directory = args.output / "runs" / args.name
    assert not (directory / "attempt-0.json").exists()
    assert (directory / "infrastructure-failure-0-test.json").exists()
    assert state.closed is True


@pytest.mark.parametrize("change", ["code", "timeout"])
def test_cached_execution_rejects_changed_code_or_timeout(experiment, change):
    prepare(experiment)
    directory = experiment / "runs/debug-1-1-hint-only"
    fingerprint = hashlib.sha256((directory / "attempt-0.py").read_bytes()).hexdigest()
    (directory / "attempt-0.json").write_text(json.dumps({"code_sha256": fingerprint, "timeout": 7200}))
    args = SimpleNamespace(output=experiment, name=directory.name, attempt=0, timeout=7200)
    if change == "code":
        (directory / "attempt-0.py").write_text("different code")
    else:
        args.timeout = 100
    with pytest.raises(ValueError, match="settings changed"):
        evaluation.execute_attempt(args)


def test_dojo_debug_uses_source_config_and_preserves_ancestral_memory(runtime, monkeypatch):
    args, state = runtime
    config_path = args.output / "config.json"
    config = json.loads(config_path.read_text())
    config["solver"] = {
        "operators": {"debug": {"llm": {"client": {"model_id": "fixture-model", "base_url": "http://original"}}}},
        "debug_memory": {},
        "time_limit_secs": 7200,
        "max_llm_call_retries": 1,
    }
    config_path.write_text(json.dumps(config))
    (args.output / "description.md").write_text("Task description")
    args.base_url = "http://debug-model/v1"
    state.execution.exit_code = 1
    evaluation.execute_attempt(args)
    calls = []

    def execute_debug(operator, client, cfg, memory, task, journal, parent, step, remaining, preview, **kwargs):
        assert cfg.operators.debug.llm.client.base_url == args.base_url
        assert cfg.operators.debug.llm.client.model_id == "fixture-model"
        assert "Task description" in task
        calls.append((list(journal), parent, step))
        return f"Repair plan {step}", f"print({step})", {"debug": step}

    modules = {
        "dojo.core.solvers.llm_helpers.generic_llm": {"GenericLLM": lambda cfg: cfg},
        "dojo.core.solvers.operators.core": {"execute_op_plan_code": execute_debug},
        "dojo.core.solvers.operators.debug": {"debug_op": object()},
        "dojo.core.solvers.operators.memory": {"create_memory_op": lambda cfg: cfg},
        "dojo.core.solvers.utils.journal": {"Journal": list, "Node": SimpleNamespace},
        "dojo.core.solvers.utils.data_preview": {"generate": lambda path: "preview"},
    }
    for name, attributes in modules.items():
        monkeypatch.setitem(sys.modules, name, SimpleNamespace(**attributes))
    monkeypatch.setenv("HINDSIGHT_API_KEY", "fixture-key")
    monkeypatch.setenv("PRIMARY_KEY", "original-key")
    monkeypatch.setenv("PRIMARY_KEY_FIXTURE_MODEL", "original-model-key")
    evaluation.repair(args)
    assert os.environ["PRIMARY_KEY_FIXTURE_MODEL"] == "fixture-key"
    assert os.environ["PRIMARY_KEY"] == "fixture-key"
    args.attempt = 1
    evaluation.execute_attempt(args)
    evaluation.repair(args)
    journal, parent, step = calls[-1]
    assert step == 2
    assert len(journal) == 2
    assert parent.parents == [journal[0]]
    assert parent.plan == "Repair plan 1"
    directory = args.output / "runs" / args.name
    assert (directory / "attempt-2.py").read_text() == "print(2)"
    assert json.loads((directory / "repair-2.json").read_text())["plan"] == "Repair plan 2"
    evaluation.repair(args)
    assert len(calls) == 2
