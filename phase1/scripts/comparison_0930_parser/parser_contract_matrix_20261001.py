"""Fixed synthetic envelope coverage, not an accuracy or speed benchmark.

Calls both native extractor stages without executing any returned program.
Does not change the already frozen patch, response text, or production source.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import platform
import signal
import sys
from pathlib import Path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canonical(code):
    return ast.dump(ast.parse(code), include_attributes=False)


def wrappers(body):
    fence = chr(96) * 3
    plan = 'A synthetic explanation.\n'
    rows = [('raw', body, 'intended_ast')]
    for indent in range(4):
        prefix = ' ' * indent
        rows.append((f'line_fence_indent_{indent}',
                     plan + prefix + fence + 'python\n' + body + prefix + fence + '\n',
                     'intended_ast_unless_body_contains_same_width_line_fence'))
    rows.extend([
        ('long_outer_fence', plan+fence+'`python\n'+body+fence+'`\n', 'intended_ast'),
        ('crlf', (plan+fence+'python\n'+body+fence+'\n').replace('\n','\r\n'),
         'intended_ast_unless_body_contains_same_width_line_fence'),
        ('four_space_indent', plan+'    '+fence+'python\n'+body+'    '+fence+'\n', 'reject'),
        ('inline_closing', plan+fence+'python\n'+body.rstrip('\n')+fence+'\n', 'reject'),
        ('unclosed', plan+fence+'python\n'+body, 'reject'),
        ('unknown_language', plan+fence+'ruby\n'+body+fence+'\n', 'reject'),
        ('closed_then_unclosed', plan+fence+'python\n'+body+fence+'\n'+fence+'python\nx=2\n', 'reject'),
    ])
    return rows


def evaluate(response, intended, first, second):
    result = {'operator_admitted': False, 'task_admitted': False, 'intended_ast_preserved': False}
    try:
        code = first.extract_code(response)
        if not code.strip():
            return result
        compile(code, '<synthetic-operator>', 'exec')
        result['operator_admitted'] = True
        final = second.extract_code(code)
        if not final.strip():
            return result
        compile(final, '<synthetic-task>', 'exec')
        result['task_admitted'] = True
        result['intended_ast_preserved'] = canonical(final) == canonical(intended)
    except Exception as error:
        result['exception_type'] = type(error).__name__
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(90)
    load('dojo.utils.python_code_blocks', args.bundle/'candidate/src/dojo/utils/python_code_blocks.py')
    modules = {}
    for name, folder in [('old', 'baseline'), ('new', 'candidate')]:
        modules[name] = (
            load(name+'_operator', args.bundle/folder/'src/dojo/core/solvers/utils/response.py'),
            load(name+'_task', args.bundle/folder/'src/dojo/utils/code_parsing.py'))
    fence = chr(96)*3
    bodies = {
        'plain': 'x=1\n',
        'unicode': 'message = "你好"\n',
        'never_execute': 'raise RuntimeError("MUST_NOT_EXECUTE")\n',
        'inline_string': 'pattern = r"'+fence+'.*?'+fence+'"\n',
        'multiline_string': 's = """\n'+fence+'\n"""\n',
    }
    rows = []
    for body_name, body in bodies.items():
        compile(body, '<synthetic-body>', 'exec')
        for envelope, response, expected in wrappers(body):
            if expected == 'intended_ast_unless_body_contains_same_width_line_fence':
                expected = 'reject' if body_name == 'multiline_string' else 'intended_ast'
            row = {'body':body_name,'envelope':envelope,'expected_new_contract':expected,
                   'response_sha256':hashlib.sha256(response.encode()).hexdigest()}
            for name, (first,second) in modules.items():
                row[name] = evaluate(response, body, first, second)
            row['new_contract_met'] = (row['new']['task_admitted'] and row['new']['intended_ast_preserved']) if expected=='intended_ast' else not row['new']['task_admitted']
            rows.append(row)
    assert len(rows)==60
    result = {'status':'SYNTHETIC_CONTRACT_MATRIX','rows':rows,'cases':len(rows),
              'contract_checks_passed':sum(x['new_contract_met'] for x in rows),
              'old_admitted_new_rejected':sum(x['old']['task_admitted'] and not x['new']['task_admitted'] for x in rows),
              'new_admitted_wrong_ast':sum(x['new']['task_admitted'] and not x['new']['intended_ast_preserved'] for x in rows),
              'python':platform.python_version(),'black':__import__('black').__version__,
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'bundle_sha256':{p.relative_to(args.bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(args.bundle.rglob('*.py'))},
              'candidate_executions':0,'model_calls':0,
              'boundary':'Synthetic format cases are not independent empirical trials or exhaustive parser proof. Stricter rejection of formerly accepted envelopes is a compatibility change, not efficacy.'}
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','bundle_sha256')}))


if __name__=='__main__':
    main()
