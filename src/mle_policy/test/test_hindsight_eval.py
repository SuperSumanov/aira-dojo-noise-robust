"""Tests for explicit prepare/evaluate stages and minimal evaluation artifacts."""

from dataclasses import dataclass
import json
import os
import sys
import subprocess
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
    directory = tmp_path / "generation/debug-1-1-hint-only"
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "case": "debug:1:1",
                "include_code": False,
                "source_journal": str(source),
                "source_config": str(tmp_path / "config.json"),
            }
        )
    )
    (directory / "nodes.json").write_text(json.dumps([{"code": "print(43)", "plan": "New plan", "metric": 0.9}]))
    return tmp_path


def test_prepare_preserves_controls_and_lists_every_artifact(experiment):
    prepare(experiment / "generation", experiment)
    manifest = json.loads((experiment / "manifest.json").read_text())
    assert len(manifest["runs"]) == 3
    assert not (experiment / "source.json").exists()
    assert (experiment / "runs/original-1/solution.py").read_text() == "raise ValueError()"
    assert (experiment / "runs/terminal-reference-1/solution.py").read_text() == "print(42)"
    for record in manifest["runs"]:
        directory = experiment / "runs" / record["name"]
        assert {path.name for path in directory.iterdir()} == {"solution.py", "metadata.json"}
        assert json.loads((experiment / record["metadata"]).read_text()) == record
        assert record["result"] == f"runs/{record['name']}/result.json"
        assert record["worker_log"] == f"runs/{record['name']}/worker-0.log"
        assert record["historical_debug_calls"] == 1
        assert record["historical_steps"] == [1, 2]
        assert record["historical_cv"] == 0.9
        assert record["historical_test"] == 0.8


def test_prepare_writes_fresh_solution(experiment):
    prepare(experiment / "generation", experiment)
    solution = experiment / "runs/original-1/solution.py"
    solution.write_text("different code")
    prepare(experiment / "generation", experiment)
    assert solution.read_text() == "raise ValueError()"


def test_prepare_adds_improvement_donor_reference(experiment):
    journal = experiment / "journal.jsonl"
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    rows.append(
        {
            "data": {
                "step": 3,
                "id": "improved",
                "parents": [2],
                "operators_used": ["improve"],
                "operators_metrics": [{}],
                "code": "print(44)",
                "plan": "Better",
                "is_buggy": False,
                "metric": 0.95,
                "metric_info/score": 0.85,
            }
        }
    )
    journal.write_text("\n".join(json.dumps(row) for row in rows))
    metadata_path = experiment / "generation/debug-1-1-hint-only/metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["case"] = "improve:1:3"
    metadata_path.write_text(json.dumps(metadata))
    prepare(experiment / "generation", experiment)
    records = json.loads((experiment / "manifest.json").read_text())["runs"]
    assert {record["variant"] for record in records} == {"hint-only", "terminal-reference", "donor-reference"}
    donor = next(record for record in records if record["variant"] == "donor-reference")
    assert donor["historical_steps"] == [3]
    assert donor["historical_cv"] == 0.95
    assert (experiment / donor["solution"]).read_text() == "print(44)"


@pytest.fixture
def chain(experiment, monkeypatch):
    prepare(experiment / "generation", experiment)
    args = SimpleNamespace(
        output=experiment,
        name="debug-1-1-hint-only",
        timeout=7200,
        cpus_per_task=8,
        max_debug_calls=4,
    )
    events = []
    outcomes = [False, True]

    def execute_attempt(args, source, record, code):
        assert source["journal"] == str(experiment / "journal.jsonl")
        assert record["name"] == args.name
        events.append(("execute", args.attempt, code))
        valid = outcomes[args.attempt]
        return {
            "attempt": args.attempt,
            "code": code,
            "valid": valid,
            "test_score": 0.7 if valid else None,
            "execution": {"exec_time": 10},
        }

    def repair(args, source, attempts):
        events.append(("repair", len(attempts)))
        assert attempts[-1]["plan"] in ("New plan", "Fixed plan", "Original", None)
        return "Fixed plan", "print(44)"

    monkeypatch.setattr(evaluation, "execute_attempt", execute_attempt)
    monkeypatch.setattr(evaluation, "repair", repair)
    return args, events, outcomes


def test_chain_repairs_in_memory_and_writes_one_result(chain):
    args, events, _ = chain
    evaluation.evaluate_chain(args)
    assert events == [("execute", 0, "print(43)"), ("repair", 1), ("execute", 1, "print(44)")]
    directory = args.output / "runs" / args.name
    assert {path.name for path in directory.iterdir()} == {"solution.py", "metadata.json", "result.json"}
    result = json.loads((directory / "result.json").read_text())
    assert [attempt["plan"] for attempt in result["attempts"]] == ["New plan", "Fixed plan"]
    assert [attempt["code"] for attempt in result["attempts"]] == ["print(43)", "print(44)"]


def test_chain_reruns_instead_of_loading_old_result(chain):
    args, events, _ = chain
    evaluation.evaluate_chain(args)
    events.clear()
    evaluation.evaluate_chain(args)
    assert events[0] == ("execute", 0, "print(43)")
    assert len(events) == 3


def test_chain_stops_at_debug_budget(chain):
    args, events, outcomes = chain
    outcomes[:] = [False] * 5
    evaluation.evaluate_chain(args)
    assert sum(event[0] == "execute" for event in events) == 5
    assert sum(event[0] == "repair" for event in events) == 4


@pytest.mark.parametrize("name", ["terminal-reference-1", "original-1"])
def test_reference_and_original_repair_budgets(chain, name):
    args, events, outcomes = chain
    args.name = name
    outcomes[:] = [False] * 5
    evaluation.evaluate_chain(args)
    expected = 1 if name.startswith("terminal") else 5
    assert sum(event[0] == "execute" for event in events) == expected


def test_zero_debug_budget(chain):
    args, events, _ = chain
    args.max_debug_calls = 0
    evaluation.evaluate_chain(args)
    assert len(events) == 1


def test_measured_summary_keeps_inherited_scores_separate(chain):
    args, _, _ = chain
    manifest = json.loads((args.output / "manifest.json").read_text())
    for record in manifest["runs"]:
        args.name = record["name"]
        evaluation.evaluate_chain(args)
    summarize(args.output)
    rows = json.loads((args.output / "results.json").read_text())
    row = next(row for row in rows if row["variant"] == "hint-only")
    assert row["historical_test"] == 0.8
    assert row["test_score"] == 0.7
    assert row["debug_calls_to_success"] == 1
    assert row["execution_seconds"] == 20
    reference = next(row for row in rows if row["variant"] == "terminal-reference")
    assert not reference["resolved"]
    assert reference["test_score"] is None


def test_evaluate_requires_explicit_prepare(experiment):
    args = SimpleNamespace(output=[experiment], local=True, workers=1)
    with pytest.raises(FileNotFoundError, match="manifest.json"):
        evaluation.evaluate(args)
    assert not (experiment / "manifest.json").exists()
    assert not (experiment / "runs").exists()


def test_evaluate_dispatches_manifest_records_and_keeps_only_worker_log(chain, monkeypatch):
    args, _, _ = chain
    output = args.output
    args.output = [output]
    args.local = True
    args.workers = 1
    commands = []

    def run(command, *, stdout, stderr, check):
        commands.append(command)
        assert check
        assert stderr == subprocess.STDOUT
        assert stdout.name.endswith("worker-0.log")
        name = command[command.index("--name") + 1]
        worker = SimpleNamespace(**{**vars(args), "output": output, "name": name})
        evaluation.evaluate_chain(worker)

    monkeypatch.setattr(evaluation.subprocess, "run", run)
    evaluation.evaluate(args)
    assert len(commands) == 3
    assert (output / "results.json").exists()
    for directory in (output / "runs").iterdir():
        assert {path.name for path in directory.iterdir()} == {
            "solution.py",
            "metadata.json",
            "result.json",
            "worker-0.log",
        }


@pytest.fixture
def runtime(experiment, monkeypatch):
    prepare(experiment / "generation", experiment)
    (experiment / "config.json").write_text(
        json.dumps(
            {
                "interpreter": {},
                "task": {"public_dir": str(experiment)},
            }
        )
    )

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
    args = SimpleNamespace(output=experiment, attempt=0, timeout=7200, cpus_per_task=8)
    manifest = json.loads((experiment / "manifest.json").read_text())
    return args, state, manifest["source"], manifest["runs"][0]


def test_dojo_execution_returns_score_and_does_not_write_extra_files(runtime, capsys):
    args, state, source, record = runtime
    result = evaluation.execute_attempt(args, source, record, "print(43)")
    assert result["valid"] is True
    assert result["test_score"] == 0.42
    assert result["code"] == "print(43)"
    assert state.code == "```python\nprint(43)\n```"
    assert state.interpreter["env"]["OMP_NUM_THREADS"] == "8"
    assert state.interpreter["working_dir"].endswith("workspace-0")
    assert state.closed is True
    assert "done" in capsys.readouterr().out
    directory = args.output / "runs" / record["name"]
    assert {path.name for path in directory.iterdir()} == {"solution.py", "metadata.json"}


@pytest.mark.parametrize("score", [None, float("nan"), float("inf"), True])
def test_missing_or_nonfinite_score_does_not_resolve_chain(runtime, score):
    args, state, source, record = runtime
    state.score = score
    result = evaluation.execute_attempt(args, source, record, "print(43)")
    assert result["valid"] is False
    assert result["test_score"] is None
    assert state.closed is True


@pytest.mark.parametrize("exit_code,timed_out", [(1, False), (0, True)])
def test_failed_execution_does_not_resolve_chain(runtime, exit_code, timed_out):
    args, state, source, record = runtime
    state.execution.exit_code = exit_code
    state.execution.timed_out = timed_out
    assert not evaluation.execute_attempt(args, source, record, "print(43)")["valid"]


def test_dojo_debug_uses_in_memory_ancestral_history(runtime, monkeypatch):
    args, state, source, record = runtime
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
    state.execution.exit_code = 1
    attempts = []
    calls = []

    def execute_debug(operator, client, cfg, memory, task, journal, parent, step, remaining, preview, **kwargs):
        assert cfg.operators.debug.llm.client.base_url == "http://original"
        assert cfg.operators.debug.llm.client.model_id == "fixture-model"
        assert "Task description" in task
        calls.append((list(journal), parent, step))
        return f"Repair plan {step}", f"print({step})", {}

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
    monkeypatch.setenv("PRIMARY_KEY", "original-key")
    monkeypatch.setenv("PRIMARY_KEY_FIXTURE_MODEL", "original-model-key")
    for attempt in range(2):
        args.attempt = attempt
        result = evaluation.execute_attempt(args, source, record, f"print({attempt})")
        result["plan"] = "Initial" if attempt == 0 else "Repair plan 1"
        attempts.append(result)
        assert evaluation.repair(args, source, attempts) == (f"Repair plan {attempt + 1}", f"print({attempt + 1})")
    assert os.environ["PRIMARY_KEY_FIXTURE_MODEL"] == "original-model-key"
    assert os.environ["PRIMARY_KEY"] == "original-key"
    journal, parent, step = calls[-1]
    assert step == 2
    assert len(journal) == 2
    assert parent.parents == [journal[0]]
    assert parent.plan == "Repair plan 1"
    directory = args.output / "runs" / record["name"]
    assert {path.name for path in directory.iterdir()} == {"solution.py", "metadata.json"}


def test_worker_failure_propagates_without_failure_reports(chain, monkeypatch):
    args, _, _ = chain
    output = args.output
    args.output = [output]
    args.local = True
    args.workers = 1

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(evaluation.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        evaluation.evaluate(args)
    assert not (output / "results.json").exists()
