"""Execute the exact _main function with actual JSON logging and fake task/solver.

No real task, model, API, GPU, or protected data. This narrowly checks final-result
delivery, not the whole Dojo runtime. Do not treat fixtures as research results.
"""
import argparse
import ast
import hashlib
import inspect
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--source-tree', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--before', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('existing receipt; no overwrite')
    os.environ.update(LOGGING_DIR='/tmp', DEFAULT_SLURM_PARTITION='gpu_24h',
        DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu',
        MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread', CUDA_VISIBLE_DEVICES='',
        PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True')
    sys.path.insert(0, str(args.source_root/'src'))
    source = args.source_root/'src/dojo/main_run.py'
    source_bytes = source.read_bytes()
    functions = [node for node in ast.parse(source_bytes).body
                 if isinstance(node, ast.FunctionDef) and node.name == '_main']
    assert len(functions) == 1
    function_code = compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec')
    cases = []
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
        from dojo.utils.logger import JsonLogger, LogEvent
        for name, final_score, no_solution in (
            ('selected_not_last_or_self_report', 0.2, False),
            ('zero_is_valid_score', 0.0, False),
            ('no_solution_no_fabricated_score', None, True),
        ):
            with tempfile.TemporaryDirectory(prefix='forets-final-result-', dir='/tmp') as folder:
                output = Path(folder)
                # Deliberately disagree with the selected node. _main must NOT
                # fetch the last graded program or maximize held-out scores.
                (output/'grading_report.json').write_text(json.dumps({'score':0.8}))
                node = NS(id='synthetic-selected', metric=NS(value=0.9, info={'score':final_score}))
                task = NS(prepare=Mock(return_value=({}, {})), close=Mock())
                interpreter = NS()
                solver = Mock(return_value=({}, None if no_solution else 'synthetic-code',
                                            None if no_solution else node))
                cfg = NS(logger=NS(output_dir=str(output), write_env_vars=False),
                         metadata=NS(), solver=NS(time_limit_secs=1800, step_limit=4),
                         task=NS(data_dir='/unread'), interpreter=NS(), save=Mock())
                actual_logger = JsonLogger(cfg, 'synthetic')
                proxy = NS(log=actual_logger.log_dict, stop=actual_logger.stop)
                def build(config, mapping, **kwargs):
                    if config is cfg.task:
                        return task
                    if config is cfg.interpreter:
                        return interpreter
                    if config is cfg.solver:
                        return solver
                    raise AssertionError('unexpected real build')
                namespace = dict(RunConfig=object, os=os, Path=Path, inspect=inspect,
                    log=logging.getLogger('synthetic-final-check'), build=build,
                    get_hardware=lambda:'synthetic', format_time=str,
                    get_slurm_identity=lambda:NS(full_id='synthetic',allocation_id='synthetic',
                                                step_id='synthetic',launcher_type='fixture'),
                    config_logger=lambda unused:proxy, TASK_MAP={}, SOLVER_MAP={},
                    INTERPRETER_MAP={}, LogEvent=LogEvent,
                    write_env_variables_to_json=Mock(side_effect=AssertionError('env export forbidden')))
                exec(function_code, namespace)
                namespace['_main'](cfg)
                event_path = output/'json/eval.jsonl'
                events = [json.loads(line)['data'] for line in event_path.read_text().splitlines()] if event_path.exists() else []
                if no_solution:
                    assert not events
                elif args.before:
                    assert events == [{}], 'expected deployed scalar-logging loss'
                else:
                    assert events == [{'score':final_score, 'selected_node_id':node.id}]
                assert task.close.call_count == 1
                assert solver.call_count == 1 and solver.load_checkpoint.call_count == 1
                assert namespace['write_env_variables_to_json'].call_count == 0
                cases.append(dict(name=name, event_count=len(events),
                                  final_score_present=bool(events and 'score' in events[0]),
                                  task_cleanup_called=True))
    result = dict(status='BUG_REPRODUCED' if args.before else 'TARGETED_PASS',
        source_tree=args.source_tree, main_run_sha256=hashlib.sha256(source_bytes).hexdigest(),
        cases=cases, gpu_jobs=0, model_loads=0, external_api_calls=0, protected_data_read=False,
        executed='unmodified _main AST function + real JsonLogger; artificial task/solver/config')
    with args.output.open('x') as file:
        json.dump(result, file, indent=2)
        file.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
