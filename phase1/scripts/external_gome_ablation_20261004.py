"""Read-only feasibility of intent/code checks; no effect or novelty claim."""
import collections
import hashlib
import json
from pathlib import Path
import re
import sys

R = Path('/research/d7/spc/yzyang4/external-gome-structure-20261004-v1')
FILES = {
    'Trace_1.json': 'ee50756cd940a1add0e44bcbb04e710233709d81f823111d70846cfe6278afb0',
    'Trace_2.json': '5a451c60ead8ac85e8eca86502cd92efe3ff1d12949510ccec394ca44dfe4cbd',
    'Trace_3.json': '8977dd468ed50d22aa173cb0aec208286e9b73142b72568861b60d55b3243ae2'}


def main():
    structure = json.loads((R/'structure.json').read_bytes())
    assert structure['status'] == 'COMPLETE'
    assert all(not f['credential_categories'] for f in structure['files'])
    keys = collections.Counter()
    paired = 0
    labels = collections.Counter()
    hits = []
    pattern = re.compile(r'\b(?:ablat\w*|remov\w*|drop|dropping|exclud\w*|without)\b', re.I)
    for name, expected in FILES.items():
        raw = (R/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        obj = json.loads(raw)
        del raw
        for task_name, task in obj.items():
            for loop_name, loop in task.items():
                if loop_name == 'scenario':
                    continue
                base, code = loop.get('base_code'), loop.get('code')
                if not isinstance(base, str) or not base.strip() or not isinstance(code, str) or not code.strip():
                    continue
                paired += 1
                # Do not render any free text, score, feedback or scenario value.
                hypothesis = loop.get('final_hypothesis')
                if isinstance(hypothesis, dict):
                    for key, value in hypothesis.items():
                        keys[(key, type(value).__name__)] += 1
                    label = hypothesis.get('problem_label')
                    if isinstance(label, str) and re.fullmatch(r'[A-Za-z0-9_ -]{1,80}', label):
                        labels[label] += 1
                    else:
                        labels['OTHER_NON_SIMPLE_LABEL'] += 1
                    proposal = hypothesis.get('hypothesis', '')
                    if isinstance(proposal, str) and pattern.search(proposal):
                        hits.append(dict(task=task_name, file=name, loop=loop_name,
                            loop_number=int(loop_name.removeprefix('loop_')),
                            hypothesis_sha256=hashlib.sha256(proposal.encode()).hexdigest(),
                            base_sha256=hashlib.sha256(base.encode()).hexdigest(),
                            code_sha256=hashlib.sha256(code.encode()).hexdigest()))
        del obj
    selected = {}
    for row in sorted(hits, key=lambda r:(r['task'], r['file'], r['loop_number'])):
        selected.setdefault(row['task'], row)
    sample = [selected[k] for k in sorted(selected)[:6]]
    result = dict(pairs=paired, hypothesis_key_types=[dict(key=k, type=t, count=n) for (k,t),n in sorted(keys.items())],
        simple_problem_labels=dict(labels), lexical_matches=len(hits), matched_tasks=len(selected), sample=sample,
        sampling='Earliest numeric loop in earliest file per task among literal removal/ablation keyword matches in hypothesis; first six task names alphabetically. Fixed before reading any source or outcome values. Not random or representative.',
        selection_regex=pattern.pattern,
        boundary='Lexical matches are not confirmed diagnostic experiments or failures. Intent/source may embed historic information; not a fully outcome-blinded scientific sample. Explicit score/feedback/scenario fields remain unopened. Six reviewed cases cannot estimate prevalence.',
        raw_content_printed=False, score_access=False, purpose='availability and fixed small intent/code sample')
    if sys.argv[1:] == ['--sample']:
        out = R/'ablation-availability-v1'
        out.mkdir(mode=0o700)
        result['source_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        result['source_files'] = FILES
        with (out/'sample.json').open('x') as f:
            json.dump(result, f, sort_keys=True, indent=2, allow_nan=False)
    else:
        assert not sys.argv[1:]
    print(json.dumps(result))


if __name__ == '__main__':
    main()
