"""Parse and compile to a code object, NEVER execute historical code."""
import ast
import hashlib


def inspect_syntax(code):
    if code is not None and not isinstance(code, str):
        raise ValueError('program_code_type')
    value = '' if code is None else code
    if len(value.encode()) > 2**20:
        raise ValueError('program_code_size')
    result = {'code_is_none': code is None, 'ast_parse_ok': False, 'compile_ok': False,
              'ast_error_sha256': None, 'compile_error_sha256': None,
              'program_executed': False}
    try:
        tree = ast.parse(value, filename='<historical-program>', mode='exec')
        second = compile(value, '<historical-program>', 'exec', flags=ast.PyCF_ONLY_AST, dont_inherit=True)
        assert ast.dump(tree, include_attributes=True) == ast.dump(second, include_attributes=True)
        result['ast_parse_ok'] = True
    except (SyntaxError, ValueError) as e:
        result['ast_error_sha256'] = hashlib.sha256(str(e).encode()).hexdigest()
    try:
        compile(value, '<historical-program>', 'exec', dont_inherit=True)
        result['compile_ok'] = True
    except (SyntaxError, ValueError) as e:
        result['compile_error_sha256'] = hashlib.sha256(str(e).encode()).hexdigest()
    return result
