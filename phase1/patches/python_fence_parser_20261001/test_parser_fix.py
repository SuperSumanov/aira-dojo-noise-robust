"""Production extraction functions and task admission, with no code execution."""
import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

helper = load('dojo.utils.python_code_blocks', ROOT/'candidate/src/dojo/utils/python_code_blocks.py')
old_response = load('baseline_response', ROOT/'baseline/src/dojo/core/solvers/utils/response.py')
old_task_parser = load('baseline_task_parser', ROOT/'baseline/src/dojo/utils/code_parsing.py')
new_response = load('candidate_response', ROOT/'candidate/src/dojo/core/solvers/utils/response.py')
new_task_parser = load('candidate_task_parser', ROOT/'candidate/src/dojo/utils/code_parsing.py')

BODY = 'import re\npattern = r"```.*?```"\ndef clean(x):\n    return re.sub(pattern, " ", x, flags=re.S)\n'
ENVELOPE = '# Plan\n\nRemove fenced text before modeling.\n\n```python\n'+BODY+'```\n'

def canonical(code):
    return ast.dump(ast.parse(code), include_attributes=False)

def task_method(parser):
    tree = ast.parse((ROOT/'baseline/src/dojo/tasks/mlebench/task.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='MLEBenchTask')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='step_task')
    empty = types.SimpleNamespace(term_out=[' '],exec_time=0,exit_code=0,eval_return=None,timed_out=False)
    ns = dict(Dict=Dict,Any=Any,Tuple=Tuple,ExecutionResult=types.SimpleNamespace(get_empty=lambda:empty),
        extract_code=parser,EXECUTION_OUTPUT='execution_output',VALIDATION_FITNESS='validation_fitness',VALID_SOLUTION='valid_solution')
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<pinned-step-task>', 'exec'),ns)
    return ns['step_task']

class ParserTests(unittest.TestCase):
    def test_original_bug_reproduces_in_operator(self):
        self.assertEqual(old_response.extract_code(ENVELOPE), '')
    def test_original_bug_reproduces_in_task(self):
        with self.assertRaisesRegex(Exception, 'not valid python'):
            old_task_parser.extract_code(BODY)
    def test_fixed_operator_preserves_ast(self):
        self.assertEqual(canonical(new_response.extract_code(ENVELOPE)), canonical(BODY))
    def test_fixed_second_extraction_is_idempotent(self):
        body = new_response.extract_code(ENVELOPE)
        self.assertEqual(new_task_parser.extract_code(body), body)
    def test_existing_plain_and_fenced_code_unchanged(self):
        for body in ('x=1\n', 'import math\nprint(math.sqrt(4))\n', 'def f():\n    return 2\n'):
            for wrapped in (body, 'Plan\n```python\n'+body+'```\n'):
                with self.subTest(body=body,wrapped=wrapped):
                    self.assertEqual(new_response.extract_code(wrapped),old_response.extract_code(wrapped))
    def test_multiple_valid_blocks_keep_existing_concatenation_policy(self):
        text='Plan\n```python\nx=1\n```\n```python\ny=2\n```\n'
        self.assertEqual(new_response.extract_code(text),old_response.extract_code(text))
    def test_invalid_body_is_not_repaired(self):
        self.assertEqual(new_response.extract_code('Plan\n```python\nx=(\n```\n'), '')
        with self.assertRaises(Exception):new_task_parser.extract_code('Plan\n```python\nx=(\n```\n')
    def test_unclosed_fence_fails_closed(self):
        self.assertEqual(new_response.extract_code('Plan\n```python\nx=1\n'), '')
    def test_empty_not_accepted(self):
        self.assertEqual(new_response.extract_code('Plan\n```python\n\n```\n'), '')
    def test_raw_whitespace_not_accepted(self):
        self.assertEqual(new_response.extract_code('\n  \n'), '')
    def test_unknown_language_skipped(self):
        self.assertEqual(new_response.extract_code('Plan\n```json\n{}\n```\n'), '')
    def test_long_fence_retains_short_fence_inside_string(self):
        body='s = """\n```\n"""\n'
        response='Plan\n````python\n'+body+'````\n'
        self.assertEqual(canonical(new_response.extract_code(response)),canonical(body))
    def test_raw_string_containing_standalone_fence_preserved(self):
        body='s = """\n```\n"""\n'
        self.assertEqual(canonical(new_response.extract_code(body)),canonical(body))
    def test_untrusted_program_never_executed(self):
        source='raise RuntimeError("must not execute")\n'
        self.assertTrue(new_response.extract_code(source))
    def test_crlf_source_bytes_preserved_before_format(self):
        code='s="```"\r\n'
        self.assertEqual(helper.python_code_blocks('Plan\r\n```python\r\n'+code+'```\r\n'),[code])
    def test_original_task_admission_is_rejection_before_interpreter(self):
        def forbidden(*a,**k):raise AssertionError('interpreter must not run')
        task=types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *a:None),_solution_script='solution.py')
        _,result=task_method(old_task_parser.extract_code)(task,{'solver_interpreter':types.SimpleNamespace(run=forbidden)},ENVELOPE)
        self.assertFalse(result['valid_solution'])
        self.assertEqual(result['execution_output'].exec_time,0)
        self.assertEqual(result['execution_output'].exit_code,0)
    def test_fixed_task_admits_exact_program_without_executing(self):
        class AdmissionObserved(Exception):pass
        called=[]
        def intercept(source,**kwargs):called.append(source);raise AdmissionObserved()
        task=types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *a:None),_solution_script='solution.py')
        with self.assertRaises(AdmissionObserved):
            task_method(new_task_parser.extract_code)(task,{'solver_interpreter':types.SimpleNamespace(run=intercept)},ENVELOPE)
        self.assertEqual(len(called),1);self.assertEqual(canonical(called[0]),canonical(BODY))

if __name__=='__main__':unittest.main()
