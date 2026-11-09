"""MLE-bench with a separately graded, agent-visible warmup subset."""

from pathlib import Path

from dojo.core.interpreters.base import ExecutionResult
from dojo.core.tasks.constants import (
    AUX_EVAL_INFO,
    EXECUTION_OUTPUT,
    TEST_FITNESS,
    VALID_SOLUTION,
    VALID_SOLUTION_FEEDBACK,
    VALIDATION_FITNESS,
)
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.tasks.mlebench.warmup.grade import WarmupGrader, append_feedback
from dojo.utils.code_parsing import extract_code


class MLEBenchTaskWarmup(MLEBenchTask):
    def __init__(self, cfg):
        directory = Path(cfg.warmup_dir).resolve()
        if Path(cfg.public_dir).resolve() != directory / "public":
            raise ValueError("Warmup public_dir must point to warmup_dir/public")
        if Path(cfg.data_dir).resolve() != directory / "public":
            raise ValueError("Warmup data_dir must point to warmup_dir/public")
        super().__init__(cfg)
        self.warmup_grader = WarmupGrader(self.competition, directory)

    def prepare(self, **task_args):
        state, task_info = super().prepare(**task_args)
        task_info["warmup"] = True
        return state, task_info

    def step_task(self, state, action):
        try:
            solution = extract_code(action)
        except Exception:
            output = ExecutionResult.get_empty()
            output.term_out = ["Invalid solution format"]
            output.exit_code = 1
            feedback = self.warmup_grader.feedback("not_scored", error="invalid_code")
            if self._submission_file_path is not None:
                self.warmup_grader.write_report(
                    self._submission_file_path,
                    Path(self.cfg.results_output_dir),
                    None,
                    feedback,
                    False,
                )
            append_feedback(output, feedback)
            return state, {EXECUTION_OUTPUT: output, VALIDATION_FITNESS: None, VALID_SOLUTION: False}
        return state, self._execute_and_grade(solution, state["solver_interpreter"])

    def _execute_and_grade(self, solution, interpreter):
        submission_path = self._submission_file_path
        if submission_path is None:
            raise ValueError("Call prepare before executing a warmup task")
        submission_path.unlink(missing_ok=True)
        try:
            output = interpreter.run(solution, file_name=self._solution_script)
            result = {EXECUTION_OUTPUT: output, VALID_SOLUTION: False}
            feedback = self.warmup_grader.feedback("not_scored", error="execution_failed")
            if output.exit_code == 0 and not output.timed_out:
                interpreter.fetch_file(submission_path)
                if submission_path.is_file():
                    report, feedback, valid = self.warmup_grader.grade(
                        submission_path,
                        Path(self.cfg.results_output_dir),
                    )
                    result[VALID_SOLUTION] = valid
                    if report is not None:
                        result[TEST_FITNESS] = report["score"]
                        result[AUX_EVAL_INFO] = report
                    result[VALID_SOLUTION_FEEDBACK] = (
                        "Submission is valid." if valid else "Submission failed format validation."
                    )
                else:
                    feedback = self.warmup_grader.feedback("not_scored", error="missing_submission")
            if AUX_EVAL_INFO not in result:
                report, _, _ = self.warmup_grader.write_report(
                    submission_path,
                    Path(self.cfg.results_output_dir),
                    None,
                    feedback,
                    False,
                )
                result[AUX_EVAL_INFO] = report
                result[TEST_FITNESS] = None
            append_feedback(output, feedback)
            return result
        finally:
            submission_path.unlink(missing_ok=True)
            if interpreter.factory:
                interpreter.close()
            else:
                interpreter.fetch_file(submission_path)

    def evaluate_fitness(self, solution=None, state=None, interpreter=None, aux_info=None):
        return self._execute_and_grade(solution, interpreter)
