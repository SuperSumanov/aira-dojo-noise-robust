"""Read-only diagnostic of one closed action; no grading or model requests."""
import ast
import hashlib
import json
import re
from pathlib import Path

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE / 'comparison-native-batch-order-20260919-hz3c589n'
SHAPES = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|AKIA[A-Z0-9]{16})')

def safe(path):
    if path.is_symlink():
        raise ValueError('symlink not admitted')
    raw = path.read_bytes()
    if SHAPES.search(raw):
        raise ValueError('credential-shaped content withheld')
    return raw

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    summary = safe(ROOT / 'summary.json')
    if digest(summary) != '711475eed488632b604f4f4c4506223427758b5d3398c5a5f31515619e8c03fb':
        raise ValueError('closed summary drift')
    ep = ROOT / 'episode-0'
    action = json.loads(safe(ep / 'action-0.json'))
    code = safe(ep / 'code-0.private.py')
    if digest(code) != action['code_sha256']:
        raise ValueError('code drift')
    analysis = safe(ep / 'analysis-0.private.json')
    output = safe(ep / 'output-0.private.log')
    tree = ast.parse(code)
    calls = dict(print=0, auc=0, score=0, split=0, cross_validation=0, fit=0, to_csv=0)
    print_metric_name = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            for category, pattern in [('print', r'(^|\.)print$'), ('auc', r'auc'), ('score', r'score'), ('split', r'split'),
                                      ('cross_validation', r'cross_val'), ('fit', r'(^|\.)fit$'), ('to_csv', r'to_csv$')]:
                calls[category] += bool(re.search(pattern, name, re.I))
            if name == 'print' and re.search(r'auc|accuracy|score|valid|cross.?val', ast.unparse(node), re.I):
                print_metric_name = True
    response = json.loads(analysis)['response']
    reason = str(response.get('summary', '')).lower()
    log = output.decode()
    patterns = {'missing_metric': r'no.{0,35}(metric|auc|score)|not.{0,35}(report|print|valid)|missing.{0,35}(metric|score)|without.{0,25}(metric|valid)',
                'validation_mentioned': r'validat|cross.validation|held.out', 'runtime_error_mentioned': r'traceback|runtime.?error|exception',
                'submission_mentioned': r'submission', 'success_mentioned': r'success|without.error|completed',
                'leakage_mentioned': r'leak|contaminat', 'missing_file_mentioned': r'file.?not.?found|no such file',
                'metric_nan_mentioned': r'\bnan\b|non.finite', 'incorrect_metric_mentioned': r'incorrect.{0,25}(metric|auc|score)'}
    print(json.dumps(dict(role='closed_development_acceptance_diagnosis_not_effect',
        summary_sha256=digest(summary), code_sha256=digest(code), analysis_sha256=digest(analysis), log_sha256=digest(output),
        analysis_is_bug=response.get('is_bug'), analysis_metric_is_null=response.get('metric') is None,
        analysis_reason_flags={name:bool(re.search(pattern, reason, re.I|re.S)) for name,pattern in patterns.items()},
        code_call_counts=calls, print_references_metric=print_metric_name,
        log_bytes=len(output), log_has_traceback='Traceback (most recent call last)' in log,
        log_has_metric_value=bool(re.search(r'(?:auc|accuracy|score|loss)\s*[:=]\s*[0-9]+[.][0-9]+',log,re.I)),
        log_mentions_validation=bool(re.search(r'validat|cross.val|auc',log,re.I))), ensure_ascii=False))

if __name__ == '__main__':
    main()
