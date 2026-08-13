from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("LOGGING_DIR", "/tmp/aira_dojo_test_logs")
os.environ.setdefault("SUPERIMAGE_DIR", ".")
os.environ.setdefault("MLE_BENCH_DATA_DIR", "/tmp/aira_dojo_test_data")
os.environ.setdefault("DEFAULT_SLURM_PARTITION", "test")
os.environ.setdefault("DEFAULT_SLURM_ACCOUNT", "test")
os.environ.setdefault("DEFAULT_SLURM_QOS", "test")

# Follow the production import order. Importing the MCTS submodule directly
# first exposes an unrelated package-initialisation cycle in the upstream repo.
import dojo.main_run as _main_run  # noqa: E402,F401
from dojo.solvers.mcts import mcts as mcts_module  # noqa: E402
from phase1.build_schema_probe_generation_manifest import (  # noqa: E402
    EXPECTED_CODE_NODES,
    EXPECTED_STEP_LIMIT,
)


class _Logger:
    def info(self, *_args, **_kwargs) -> None:
        pass

    def error(self, *_args, **_kwargs) -> None:
        pass


@pytest.mark.parametrize(
    ("step_limit", "expected_expansions"),
    [(1, 0), (2, 1)],
)
def test_root_consumes_one_journal_step_without_empty_iteration(
    monkeypatch: pytest.MonkeyPatch,
    step_limit: int,
    expected_expansions: int,
) -> None:
    solver = object.__new__(mcts_module.MCTS)
    solver.cfg = SimpleNamespace(step_limit=step_limit, time_limit_secs=1200)
    solver.state = SimpleNamespace(current_step=0, running_time=0.0)
    solver.logger = _Logger()
    solver.journal = SimpleNamespace(get_best_node=lambda: None)
    calls: list[int] = []

    def create_root_node() -> None:
        solver.state.current_step = 1

    def step(_task: object, state: object) -> object:
        calls.append(solver.state.current_step)
        assert solver.remaining_steps == 1
        solver.state.current_step += 1
        return state

    monkeypatch.setattr(solver, "create_root_node", create_root_node)
    monkeypatch.setattr(solver, "step", step)
    monkeypatch.setattr(solver, "save_checkpoint", lambda: None)
    monkeypatch.setattr(mcts_module, "export_search_results", lambda *_args, **_kwargs: None)

    state = object()
    returned_state, code, node = mcts_module.MCTS.__call__(solver, object(), state)

    assert returned_state is state
    assert code is None
    assert node is None
    assert len(calls) == expected_expansions
    assert solver.state.current_step == step_limit


def test_schema_generation_manifest_accepts_exactly_one_candidate_budget() -> None:
    """Keep the post-generation audit aligned with root-plus-candidate accounting."""
    assert EXPECTED_STEP_LIMIT == 2
    assert EXPECTED_CODE_NODES == 1
