"""Module-scope generation for a shared untuned initial program.

AST assembly is not a security boundary. Generated modules may contain arbitrary
model/feature code. No label, outcome, metric or observed-score based edits.
"""
import ast
import hashlib
import textwrap

PROTOCOL = 'model_module_v1'
MODES = ('whole_program', 'model_module')
HEADER = 'EScope execution interface (takes precedence over the generic output format):'
INSTRUCTION = '''Return a short plan and one Python code block containing ONLY
def build_model(X):
    ...
X is a pandas feature DataFrame used to describe the input schema. Return an
unfitted sklearn-compatible classifier or pipeline supporting fit, predict,
predict_proba and classes_. Feature engineering, preprocessing, models, ensembles,
local imports, nested classes and helper functions may all be implemented inside
this function. Do not return or execute training, validation, data loading or
submission code outside it: the existing outer program will run those unchanged.
The full prior program and its feedback are context. Change its build_model
function to improve performance or repair the reported error. The whole returned
pipeline must fit in the stated execution limit. Do not access external evaluation
files or change the validation split, metric, label ordering, or submission schema.
Return real executable code, not an ellipsis, example, placeholder or pseudocode.'''


def code_for(task):
    from dojo.solvers.fore_ts import common_start
    # This module replaces common_start.code_for in the new source tree. The
    # original function is retained under original_code_for, not called recursively.
    raw = common_start.original_code_for(task)
    begin = raw.index('categorical = ')
    end = raw.index('X_train, X_valid, y_train, y_valid = ')
    chunk = raw[begin:end]
    # Keep the exact categorical coercion outside the editable model builder.
    split = chunk.index('preprocess = ')
    schema = chunk[:split]
    model = chunk[split:].replace('model = make_pipeline(', 'return make_pipeline(')
    function = 'def build_model(X):\n' + textwrap.indent(
        "categorical = list(X.select_dtypes(include=['object', 'category', 'bool']).columns)\n"
        "numeric = [c for c in X.columns if c not in categorical]\n" + model, '    ')
    return raw[:begin] + schema + '\n' + function + '\nmodel = build_model(X)\n' + raw[end:]


def module_node(code):
    tree = ast.parse(code)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('return_exactly_one_build_model_function')
    node = tree.body[0]
    args = node.args
    if (node.name != 'build_model' or node.decorator_list or node.returns is not None
        or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults
        or len(args.args) != 1 or args.args[0].arg != 'X' or args.args[0].annotation is not None):
        raise ValueError('expected_unannotated_build_model_X_without_defaults')
    return node


def assemble(template, output):
    base = ast.parse(template)
    places = [i for i, n in enumerate(base.body) if isinstance(n, ast.FunctionDef) and n.name == 'build_model']
    if len(places) != 1:
        raise ValueError('exact_template_function_required')
    before = ast.dump(ast.Module(body=[n for i, n in enumerate(base.body) if i != places[0]], type_ignores=[]))
    try:
        node = module_node(output)
        accepted = True
        reason = None
    except (SyntaxError, ValueError) as exc:
        # A failed proposal is still executed and recorded under the native
        # debug allowance. It is never silently replaced by the baseline.
        reason = str(exc) if isinstance(exc, ValueError) else 'invalid_python_syntax'
        node = ast.parse('def build_model(X):\n    raise RuntimeError("EScope interface failure: '+reason+'")').body[0]
        accepted = False
    base.body[places[0]] = node
    ast.fix_missing_locations(base)
    code = ast.unparse(base) + '\n'
    after_tree = ast.parse(code)
    after = ast.dump(ast.Module(body=[n for i, n in enumerate(after_tree.body) if i != places[0]], type_ignores=[]))
    if before != after:
        raise ValueError('outer_program_changed_during_assembly')
    compile(code, '<assembled_model_module>', 'exec')
    return code, dict(interface_accepted=accepted, rejection=reason,
        outer_ast_sha256=hashlib.sha256(before.encode()).hexdigest(),
        output_sha256=hashlib.sha256(output.encode()).hexdigest())


def process(solver, code, metrics):
    mode = getattr(solver.cfg, 'edit_scope', 'whole_program')
    if mode == 'whole_program':
        return code, metrics
    if mode != 'model_module':
        raise ValueError('unknown_edit_scope')
    result, receipt = assemble(code_for(solver.task_name), code)
    return result, dict(metrics, edit_scope=receipt)


def apply_config(cfg, mode):
    if mode not in MODES:
        raise ValueError('frozen_edit_scope')
    cfg['solver']['edit_scope'] = mode
    for name in ('draft', 'improve', 'debug'):
        field = cfg['solver']['operators'][name]['system_message_prompt_template']
        if HEADER in field['template']:
            raise ValueError('already_applied')
        if mode == 'model_module':
            field['template'] += '\n\n' + HEADER + '\n' + INSTRUCTION
    return cfg
