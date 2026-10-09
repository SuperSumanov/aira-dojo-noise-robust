"""Read-only shape diagnosis of the CLOSED development exposure batch.

Never exports response/code/prompt text or arbitrary exception messages. Syntax
recovery means only parseable text exists, NOT a correct/safe working program.
No changes to native extraction, outcomes, qualification, or live runtime.
"""
import ast
from collections import Counter
import hashlib
import importlib.util
import json
import re
from exposure_opportunity_readout import ROOT, PLAN
from lifecycle_pilot import read, sha, write
from live_readout import lines


def syntax_shape(text):
    try:
        tree = ast.parse(text)
        return dict(parseable=True, nonempty=bool(tree.body), error=None)
    except (SyntaxError, ValueError) as exc:
        msg = str(exc).lower()
        category = next((label for term, label in (
            ('unterminated', 'unterminated'), ('never closed', 'unclosed'),
            ('indent', 'indentation'), ('invalid syntax', 'invalid_syntax'),
            ('null bytes', 'null_byte')) if term in msg), 'other_parse_error')
        return dict(parseable=False, nonempty=False, error=category)


def shape(response, native_code, extract, parse_thinking):
    if not isinstance(response, str) or not isinstance(native_code, str):
        raise ValueError('text schema')
    thinking, answer = parse_thinking(response)
    extracted = extract(native_code)
    native_fences = re.findall(r'```(python)?\n*(.*?)\n*```', answer, re.DOTALL)
    # Alternative delimiters are examined only, never executed or substituted.
    general_fences = re.findall(r'```[^\n]*\n(.*?)\n?```', answer, re.DOTALL)
    native_valid = sum(syntax_shape(body)['parseable'] and bool(body.strip()) for _, body in native_fences)
    alternative_valid = sum(syntax_shape(body)['parseable'] and bool(body.strip()) for body in general_fences)
    if extracted.strip():
        category = 'nonempty_native_execution'
    elif not response.strip():
        category = 'empty_response'
    elif not answer.strip() and thinking:
        category = 'thinking_without_answer'
    elif native_fences:
        category = 'native_fences_rejected_or_empty'
    else:
        category = 'no_native_fence_nonpython_answer'
    return dict(category=category, response_characters=len(response),
        answer_characters=len(answer), thinking_characters=len(thinking),
        journal_code_characters=len(native_code), executed_characters=len(extracted),
        fence_markers=answer.count('```'), native_fences=len(native_fences),
        native_parseable_nonempty_fences=native_valid,
        alternative_parseable_nonempty_fences=alternative_valid,
        whole_answer=syntax_shape(answer),
        native_fence_errors=dict(Counter(syntax_shape(body)['error'] or 'parseable' for _, body in native_fences)),
        alternative_syntax_is_not_execution_evidence=True)


def main():
    if sha(ROOT/'plan.json') != PLAN or not (ROOT/'closed.json').exists():
        raise ValueError('exact closed development batch')
    plan = read(ROOT/'plan.json')
    source_name = 'source/src/dojo/core/solvers/utils/response.py'
    source = ROOT/source_name
    if sha(source) != plan['files'][source_name]:
        raise ValueError('frozen native extractor drift')
    spec = importlib.util.spec_from_file_location('frozen_response_shape', source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    rows = []
    for assignment in plan['schedule']:
        ep = ROOT/f'episode-{assignment["index"]}'
        journal_path = ep/'checkpoint/journal.jsonl'
        nodes = [n for n in lines(journal_path) if n.get('operators_used')]
        candidates = sorted([read(p) for p in ep.glob('candidate-*.json')
                             if '.private.' not in p.name], key=lambda c:c['elapsed_seconds'])
        if len(nodes) != len(candidates):
            raise ValueError('full sequence denominator')
        details = []
        for ordinal, (node, candidate) in enumerate(zip(nodes, candidates)):
            native_code = node['code']
            if hashlib.sha256(module.extract_code(native_code).encode()).hexdigest() != candidate['code_sha256']:
                raise ValueError('exact executed sequence mismatch')
            metrics = node['operators_metrics'][0]
            response = metrics['completion_text']
            usage = metrics.get('usage', {})
            token_counts = {k: v for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                            if type(v := usage.get(k)) is int and v >= 0}
            details.append(dict(ordinal=ordinal, **shape(response, native_code,
                module.extract_code, module.parse_thinking_tags), token_counts=token_counts))
        rows.append(dict(index=assignment['index'], task=assignment['task'],
            nodes=len(nodes), journal_sha256=sha(journal_path),
            categories=dict(Counter(d['category'] for d in details)), details=details))
    result = dict(plan_sha256=PLAN, analysis_sha256=sha(__file__),
        native_extractor_sha256=sha(source), rows=rows,
        boundary='Post-outcome structural diagnosis only; no raw text exported, no candidate executed, no outcome or gate changed. Saved last operator response does not account for earlier extraction retries. Token count alone does not prove truncation without a recorded finish reason.')
    dest = ROOT/'response-shape-diagnosis-v1.json'
    write(dest, result)
    print(json.dumps(dict(sha256=sha(dest), rows=[{k:r[k] for k in ('index','task','nodes','categories')} for r in rows]), sort_keys=True))


if __name__ == '__main__':
    main()
