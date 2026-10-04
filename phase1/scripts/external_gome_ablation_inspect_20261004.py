"""Inspect six fixed source pairs; no downloaded code execution or score fields."""
import argparse
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re

R = Path('/research/d7/spc/yzyang4/external-gome-structure-20261004-v1')
SOURCE_SHA = 'ee50756cd940a1add0e44bcbb04e710233709d81f823111d70846cfe6278afb0'
SAMPLE_SOURCE = 'f468c80dc56c4eef35858c7a65b5fb13b27bc4e28176f8509565014aceca6970'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=int, choices=range(6), required=True)
    parser.add_argument('--full', choices=['base', 'code'])
    parser.add_argument('--offset', type=int, default=0)
    args = parser.parse_args()
    assert args.offset >= 0
    sample = json.loads((R/'ablation-availability-v1/sample.json').read_bytes())
    assert sample['source_script_sha256'] == SAMPLE_SOURCE and len(sample['sample']) == 6
    row = sample['sample'][args.index]
    assert row['file'] == 'Trace_1.json'
    raw = (R/row['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    assert not any(f['credential_categories'] for f in json.loads((R/'structure.json').read_bytes())['files'])
    loop = json.loads(raw)[row['task']][row['loop']]
    base, code, hypothesis = loop['base_code'], loop['code'], loop['final_hypothesis']['hypothesis']
    for value, field in ((base, 'base'), (code, 'code'), (hypothesis, 'hypothesis')):
        assert hashlib.sha256(value.encode()).hexdigest() == row[field+'_sha256']
    # This is not a claim of complete blindness: proposed hypotheses can refer to
    # history qualitatively. Numeric prose is suppressed; score fields untouched.
    prose = re.sub(r'(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', '<number>', hypothesis)
    print(json.dumps(dict(index=args.index, task=row['task'], loop=row['loop'], hypothesis_numeric_masked=prose,
                         base_lines=len(base.splitlines()), code_lines=len(code.splitlines()))))
    try:
        bt, ct = ast.parse(base), ast.parse(code)
    except SyntaxError as error:
        print(json.dumps(dict(parse='FAIL', error_type=type(error).__name__)))
        return
    if args.full:
        print(ast.unparse(bt if args.full == 'base' else ct))
    else:
        before, after = ast.unparse(bt).splitlines(), ast.unparse(ct).splitlines()
        diff = list(difflib.unified_diff(before, after, fromfile='base_AST', tofile='candidate_AST', n=3))
        print(json.dumps(dict(diff_lines=len(diff), offset=args.offset, truncated=len(diff)>args.offset+340)))
        print('\n'.join(diff[args.offset:args.offset+340]))


if __name__ == '__main__':
    main()
