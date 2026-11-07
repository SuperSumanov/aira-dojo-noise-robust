"""Evaluate hindsight rewrites, automatically debugging failures until valid or exhausted."""

import argparse
import concurrent.futures
import dataclasses
import fcntl
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from ..helper import atomic_json
from .prepare import prepare
from .summarize import summarize


def execute_attempt(args):
    """Execute unchanged solution code and persist its official MLEBench result."""
    directory = args.output / "runs" / args.name
    result_path = directory / f"attempt-{args.attempt}.json"
    code_path = directory / f"attempt-{args.attempt}.py"
    fingerprint = hashlib.sha256(code_path.read_bytes()).hexdigest()
    if result_path.exists():
        previous = json.loads(result_path.read_text())
        if previous["code_sha256"] != fingerprint or previous["timeout"] != args.timeout:
            raise ValueError(f"Execution settings changed: {result_path}")
        print(f"Already executed: {result_path}")
        return previous
    from omegaconf import OmegaConf

    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.core.interpreters.jupyter.jupyter_interpreter import JupyterInterpreter
    from dojo.core.tasks.constants import EXECUTION_OUTPUT, TEST_FITNESS, VALID_SOLUTION
    from dojo.tasks.mlebench.task import MLEBenchTask

    source = json.loads((args.output / "source.json").read_text())
    config = json.loads(Path(source["config"]).read_text())
    identity = f"{args.attempt}-{os.environ.get('SLURM_JOB_ID', 'local')}"
    workspace = (directory / f"workspace-{identity}").resolve()
    interpreter_config = dict(config["interpreter"], working_dir=str(workspace), timeout=args.timeout)
    interpreter_config["env"] = dict(
        interpreter_config.get("env", {}),
        OMP_NUM_THREADS=str(args.cpus_per_task),
        MKL_NUM_THREADS=str(args.cpus_per_task),
        OPENBLAS_NUM_THREADS=str(args.cpus_per_task),
        TOKENIZERS_PARALLELISM="false",
    )
    task_config = OmegaConf.create(dict(config["task"], results_output_dir=str(directory.resolve() / "grading")))
    interpreter = JupyterInterpreter(JupyterInterpreterConfig(**interpreter_config), Path(task_config.public_dir))
    task = MLEBenchTask(task_config)
    state, _ = task.prepare(solver_interpreter=interpreter)
    started = time.time()
    try:
        probe = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,uuid,name", "--format=csv,noheader"],
            text=True,
        )
        (directory / f"gpu-{identity}.log").write_text(probe, encoding="utf-8")
        state, evaluation = task.step_task(state, f"```python\n{code_path.read_text()}\n```")
        execution = evaluation.pop(EXECUTION_OUTPUT)
        if "Kernel did not become ready in time." in "".join(execution.term_out):
            atomic_json(directory / f"infrastructure-failure-{identity}.json", dataclasses.asdict(execution))
            raise RuntimeError("Jupyter kernel readiness failure; solution did not execute")
        (directory / f"attempt-{args.attempt}.log").write_text("".join(execution.term_out), encoding="utf-8")
        score = evaluation.get(TEST_FITNESS)
        valid_score = isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score)
        result = {
            "name": args.name,
            "attempt": args.attempt,
            "code_sha256": fingerprint,
            "timeout": args.timeout,
            "started_at": started,
            "finished_at": time.time(),
            "job_id": os.environ.get("SLURM_JOB_ID"),
            "host": os.uname().nodename,
            "step_id": os.environ.get("SLURM_STEP_ID"),
            "step_gpus": os.environ.get("SLURM_STEP_GPUS"),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "gpu_probe": probe,
            "execution": dataclasses.asdict(execution),
            "evaluation": evaluation,
            "valid": bool(evaluation.get(VALID_SOLUTION))
            and execution.exit_code == 0
            and not execution.timed_out
            and valid_score,
            "test_score": score if valid_score else None,
        }
        atomic_json(result_path, result)
        print(
            f"DONE {args.name} attempt={args.attempt} valid={result['valid']} score={result['test_score']}", flush=True
        )
        return result
    finally:
        task.close(state)


def repair(args) -> None:
    """Generate the next attempt with dojo's debug operator and ancestral memory."""
    from omegaconf import OmegaConf

    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from dojo.core.solvers.operators.core import execute_op_plan_code
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.operators.memory import create_memory_op
    from dojo.core.solvers.utils.journal import Journal, Node
    from dojo.core.solvers.utils.data_preview import generate

    if not 0 <= args.attempt < 4:
        raise ValueError("This experiment allows four repairs per solution")
    directory = args.output / "runs" / args.name
    next_path = directory / f"attempt-{args.attempt + 1}.py"
    if next_path.exists():
        print(f"Already generated: {next_path}")
        return
    source = json.loads((args.output / "source.json").read_text())
    metadata = json.loads((directory / "metadata.json").read_text())
    config = json.loads(Path(source["config"]).read_text())
    cfg = OmegaConf.create(config["solver"])
    if args.base_url is not None:
        cfg.operators.debug.llm.client.base_url = args.base_url
    if "HINDSIGHT_API_KEY" in os.environ:
        model = cfg.operators.debug.llm.client.model_id.replace("-", "_").replace(".", "_").upper()
        os.environ["PRIMARY_KEY_" + model] = os.environ["HINDSIGHT_API_KEY"]
        os.environ["PRIMARY_KEY"] = os.environ["HINDSIGHT_API_KEY"]
    journal = Journal()
    parent = None
    elapsed = 0
    for attempt in range(args.attempt + 1):
        result = json.loads((directory / f"attempt-{attempt}.json").read_text())
        if result["valid"]:
            raise ValueError("Cannot debug a successful solution")
        node = Node(
            code=(directory / f"attempt-{attempt}.py").read_text(),
            plan=(
                metadata["plan"]
                if attempt == 0
                else json.loads((directory / f"repair-{attempt}.json").read_text())["plan"]
            ),
            step=attempt,
            parents=[parent] if parent else [],
            operators_used=["debug" if attempt else "draft"],
            is_buggy=True,
            _term_out=result["execution"]["term_out"],
            analysis="Execution failed or did not produce a valid submission.",
        )
        journal.append(node)
        parent = node
        elapsed += result["finished_at"] - result["started_at"]
    task_description = Path(config["task"]["public_dir"], "description.md").read_text()
    instructions = Path("src/dojo/tasks/mlebench/instructions.txt").read_text()
    plan, code, metrics = execute_op_plan_code(
        debug_op,
        GenericLLM(cfg.operators.debug),
        cfg,
        create_memory_op(cfg.debug_memory),
        os.path.expandvars(instructions) + "\n" + task_description,
        journal,
        parent,
        args.attempt + 1,
        max(7200, int(cfg.time_limit_secs - elapsed)),
        generate(Path(config["task"]["public_dir"])),
        max_operator_tries=cfg.max_llm_call_retries,
    )
    if not code:
        raise ValueError("Debug operator did not return code")
    atomic_json(directory / f"repair-{args.attempt + 1}.json", {"plan": plan, "metrics": metrics})
    next_path.write_text(code, encoding="utf-8")
    print(f"REPAIRED {args.name} attempt={args.attempt + 1}", flush=True)


def pending_runs(output):
    """Find unfinished chains, including failures whose next repair is not generated yet."""
    manifest = json.loads((output / "manifest.json").read_text())
    pending = []
    for record in manifest["runs"]:
        directory = output / "runs" / record["name"]
        for attempt in range(5):
            result_path = directory / f"attempt-{attempt}.json"
            if not result_path.exists():
                pending.append(record["name"])
                break
            result = json.loads(result_path.read_text())
            if result["valid"] or record["variant"] in ("terminal-reference", "donor-reference"):
                break
    return pending


def evaluate_chain(args):
    """Resume one chain under a lock; preserve failures and stop at its first valid score."""
    directory = args.output / "runs" / args.name
    metadata = json.loads((directory / "metadata.json").read_text())
    with (directory / "chain.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for attempt in range(5):
            args.attempt = attempt
            result = execute_attempt(args)
            if result["valid"]:
                return True
            if attempt == 4 or metadata["variant"] in ("terminal-reference", "donor-reference"):
                return False
            repair(args)


def evaluate(args):
    """Prepare and evaluate multiple result directories using one worker per GPU."""
    if args.local and args.workers != 1:
        raise ValueError("Local execution requires --workers 1; use Slurm for isolated parallel GPUs")
    if not args.local:
        os.environ["SLURM_JOB_ID"]
    for output in args.output:
        if not (output / "manifest.json").exists():
            prepare(output)
    pending = [(output, name) for output in args.output for name in pending_runs(output)]

    def one(item):
        output, name = item
        command = (
            []
            if args.local
            else [
                "srun",
                f"--jobid={os.environ['SLURM_JOB_ID']}",
                "--exclusive",
                "--nodes=1",
                "--ntasks=1",
                "--gres=gpu:1",
                f"--cpus-per-task={args.cpus_per_task}",
            ]
        )
        command.extend(
            [
                sys.executable,
                "-u",
                "-m",
                "mle_policy.src.data.hindsight.exp.evaluate",
                "--output",
                str(output),
                "--name",
                name,
                "--timeout",
                str(args.timeout),
                "--cpus-per-task",
                str(args.cpus_per_task),
            ]
        )
        if args.base_url is not None:
            command.extend(["--base-url", args.base_url])
        with (output / "runs" / name / "chain-worker.log").open("a") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        print(f"CHAIN {output}/{name} exit={result.returncode}", flush=True)
        return result.returncode

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            statuses = list(pool.map(one, pending))
    finally:
        for output in args.output:
            summarize(output)
    if any(statuses):
        raise RuntimeError("Some chains failed or exhausted repairs; inspect results.json and chain-worker.log")
    for output in args.output:
        rows = json.loads((output / "results.json").read_text())
        if any(not row["resolved"] for row in rows):
            raise RuntimeError(f"Unresolved solutions remain in {output / 'results.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, nargs="+", required=True, help="Evaluation directories containing source.json"
    )
    parser.add_argument("--timeout", type=int, default=7200, help="Seconds per execution attempt")
    parser.add_argument("--workers", type=int, default=2, help="Concurrent single-GPU Slurm workers")
    parser.add_argument("--cpus-per-task", type=int, default=8)
    parser.add_argument("--base-url", help="Debug model endpoint; defaults to source config")
    parser.add_argument("--local", action="store_true", help="Execute serially on the current GPU without srun")
    parser.add_argument("--name", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min(args.timeout, args.workers, args.cpus_per_task) <= 0:
        parser.error("timeout, workers, and cpus-per-task must be positive")
    if args.name is not None:
        if len(args.output) != 1:
            parser.error("A chain worker requires exactly one output directory")
        args.output = args.output[0]
        return 0 if evaluate_chain(args) else 1
    evaluate(args)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
