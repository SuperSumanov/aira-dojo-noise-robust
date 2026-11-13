"""Execute prepared cases on GPUs, with optional dojo debugging of failed code.

Input --output: prepare.py output containing manifest.json and runs/<name>/
solution.py and metadata.json. Paths are relative to this evaluation directory.
Output: runs/<name>/result.json (all executed attempts, code and execution output),
runs/<name>/worker-0.log (dojo log), and results.json (one row per solution).
Dojo creates workspace-<attempt>/ and grading/ under each run for task execution.
"""

import argparse
import concurrent.futures
import dataclasses
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from dotenv import load_dotenv

from ..helper import write_json
from .summarize import summarize


def execute_attempt(args, source, record, code):
    """Execute one program through dojo and return its measured result in memory."""
    from omegaconf import OmegaConf

    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.core.interpreters.jupyter.jupyter_interpreter import JupyterInterpreter
    from dojo.core.tasks.constants import EXECUTION_OUTPUT, TEST_FITNESS, VALID_SOLUTION
    from dojo.tasks.mlebench.task import MLEBenchTask

    directory = args.output / "runs" / record["name"]
    config = json.loads(Path(source["config"]).read_text())
    interpreter_config = dict(
        config["interpreter"],
        working_dir=str((directory / f"workspace-{args.attempt}").resolve()),
        timeout=args.timeout,
    )
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
        state, evaluation = task.step_task(state, f"```python\n{code}\n```")
        execution = evaluation.pop(EXECUTION_OUTPUT)
        print("".join(execution.term_out), flush=True)
        score = evaluation.get(TEST_FITNESS)
        valid_score = isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score)
        result = {
            "attempt": args.attempt,
            "code": code,
            "started_at": started,
            "finished_at": time.time(),
            "execution": dataclasses.asdict(execution),
            "evaluation": evaluation,
            "valid": bool(evaluation.get(VALID_SOLUTION))
            and execution.exit_code == 0
            and not execution.timed_out
            and valid_score,
            "test_score": score if valid_score else None,
        }
        print(
            f"DONE {record['name']} attempt={args.attempt} valid={result['valid']} score={result['test_score']}",
            flush=True,
        )
        return result
    finally:
        task.close(state)


def repair(args, source, attempts):
    """Use dojo's debug operator with the code and execution history held in memory."""
    from omegaconf import OmegaConf

    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from dojo.core.solvers.operators.core import execute_op_plan_code
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.operators.memory import create_memory_op
    from dojo.core.solvers.utils.data_preview import generate
    from dojo.core.solvers.utils.journal import Journal, Node

    config = json.loads(Path(source["config"]).read_text())
    cfg = OmegaConf.create(config["solver"])
    if args.base_url is not None:
        cfg.operators.debug.llm.client.base_url = args.base_url
    if args.model_id is not None:
        cfg.operators.debug.llm.client.model_id = args.model_id
    load_dotenv()
    journal = Journal()
    parent = None
    for result in attempts:
        node = Node(
            code=result["code"],
            plan=result["plan"],
            step=result["attempt"],
            parents=[parent] if parent else [],
            operators_used=["debug" if result["attempt"] else "draft"],
            is_buggy=True,
            _term_out=result["execution"]["term_out"],
            analysis="Execution failed or did not produce a valid submission.",
        )
        journal.append(node)
        parent = node
    task_description = Path(config["task"]["public_dir"], "description.md").read_text()
    instructions = Path("src/dojo/tasks/mlebench/instructions.txt").read_text()
    elapsed = sum(result["finished_at"] - result["started_at"] for result in attempts)
    plan, code, _ = execute_op_plan_code(
        debug_op,
        GenericLLM(cfg.operators.debug),
        cfg,
        create_memory_op(cfg.debug_memory),
        os.path.expandvars(instructions) + "\n" + task_description,
        journal,
        parent,
        len(attempts),
        max(7200, int(cfg.time_limit_secs - elapsed)),
        generate(Path(config["task"]["public_dir"])),
        max_operator_tries=cfg.max_llm_call_retries,
    )
    if not code:
        raise ValueError("Debug operator did not return code")
    return plan, code


def evaluate_chain(args):
    """Run one prepared solution and up to max-debug-calls repairs, then save one result."""
    manifest = json.loads((args.output / "manifest.json").read_text())
    record = next(record for record in manifest["runs"] if record["name"] == args.name)
    metadata = json.loads((args.output / record["metadata"]).read_text())
    code = (args.output / record["solution"]).read_text()
    plan = metadata["plan"]
    attempts = []
    budget = 0 if metadata["variant"] in ("terminal-reference", "donor-reference") else args.max_debug_calls
    for attempt in range(budget + 1):
        args.attempt = attempt
        result = execute_attempt(args, manifest["source"], record, code)
        result["plan"] = plan
        attempts.append(result)
        if result["valid"] or attempt == budget:
            break
        plan, code = repair(args, manifest["source"], attempts)
    write_json(args.output / record["result"], {"name": args.name, "attempts": attempts})


def evaluate(args):
    """Consume existing manifests and execute every solution once with one worker per GPU."""
    if args.local and args.workers != 1:
        raise ValueError("Local execution requires --workers 1")
    pending = []
    for output in args.output:
        manifest = json.loads((output / "manifest.json").read_text())
        pending.extend((output, record) for record in manifest["runs"])

    def one(item):
        output, record = item
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
                record["name"],
                "--timeout",
                str(args.timeout),
                "--cpus-per-task",
                str(args.cpus_per_task),
                "--max-debug-calls",
                str(args.max_debug_calls),
            ]
        )
        if args.base_url is not None:
            command.extend(["--base-url", args.base_url])
        if args.model_id is not None:
            command.extend(["--model-id", args.model_id])
        with (output / record["worker_log"]).open("w") as stream:
            subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
        print(f"DONE {output}/{record['name']}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, pending))
    for output in args.output:
        summarize(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, nargs="+", required=True, help="Prepared directories with manifest.json"
    )
    parser.add_argument("--timeout", type=int, default=7200, help="Seconds per program execution")
    parser.add_argument("--workers", type=int, default=2, help="Concurrent single-GPU Slurm workers")
    parser.add_argument("--cpus-per-task", type=int, default=8, help="CPU threads per GPU worker")
    parser.add_argument("--max-debug-calls", type=int, default=4, help="Repairs after a failed initial execution")
    parser.add_argument("--base-url", help="Override the debug model service URL for all prepared runs")
    parser.add_argument("--model-id", help="Override the debug model ID for all prepared runs")
    parser.add_argument("--local", action="store_true", help="Execute on the current GPU; use --workers 1")
    parser.add_argument("--name", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.name is not None:
        args.output = args.output[0]
        evaluate_chain(args)
    else:
        evaluate(args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
