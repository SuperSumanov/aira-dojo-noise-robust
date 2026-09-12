"""Exact source hooks for passive, complete-iteration incumbent receipts."""
from forets_paid_patch_20260911 import once

MODULE = 'dojo.solvers.fore_ts.wallclock'


def patch_mcts(source):
    if MODULE in source:
        raise ValueError('wallclock hook already installed')
    source = once(source, '        node.absorb_exec_result(eval_result[EXECUTION_OUTPUT])',
        '        from '+MODULE+' import remember_submission\n'
        '        remember_submission(node, eval_result)\n'
        '        node.absorb_exec_result(eval_result[EXECUTION_OUTPUT])')
    return once(source, '            state = self.step(task, state)\n',
        '            state = self.step(task, state)\n'
        '            from '+MODULE+' import checkpoint_incumbent\n'
        '            checkpoint_incumbent(self)\n')


def patch_task(source):
    if MODULE in source:
        raise ValueError('wallclock hook already installed')
    begin = '                test_fitness, report = evaluate.evaluate_submission(\n'
    end = '                eval_result[TEST_FITNESS] = test_fitness\n'
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError('task archive hook anchor changed')
    start = source.index(begin); stop = source.index(end, start)
    original = source[start:stop]
    replacement = ('                from '+MODULE+' import submission_context\n'
                   '                with submission_context(action, solution) as binding:\n' +
                   ''.join('    '+line if line.strip() else line for line in original.splitlines(True)) +
                   '                if binding is not None:\n'
                   '                    eval_result["_forets_submission_archive"] = binding["receipt"]\n')
    return source[:start] + replacement + source[stop:]


def patch_archive(source):
    if MODULE in source:
        raise ValueError('wallclock hook already installed')
    return once(source, '    return receipt\n',
        '    from '+MODULE+' import capture_submission\n'
        '    capture_submission(leaf, receipt)\n'
        '    return receipt\n')


def patch_budget(source):
    if MODULE in source:
        raise ValueError('wallclock hook already installed')
    anchor = 'def reserve(path, scope, attempt_id, amount=None):\n'
    return once(source, anchor, anchor + '    from '+MODULE+' import admit_request\n    admit_request()\n')


def patch_supervisor(source):
    if 'search_start_ns' in source:
        raise ValueError('cutoff clock already installed')
    return once(source, '    started = time.monotonic()\n',
        '    started_ns = time.monotonic_ns()\n'
        '    started = started_ns / 10**9\n'
        '    if environment and environment.get("FORETS_SEARCH_SECONDS"):\n'
        '        if float(environment["FORETS_SEARCH_SECONDS"]) != wall_seconds:\n'
        '            raise ValueError("supervisor and search cutoff differ")\n'
        '        environment = dict(environment, FORETS_SEARCH_START_NS=str(started_ns))\n'
        '        summary.update(search_start_ns=started_ns, search_seconds=wall_seconds)\n')
