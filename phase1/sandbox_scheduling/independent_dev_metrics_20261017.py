"""Read-only, separately implemented metrics for two CLOSED approved DEV batches.

No production scorer, pandas, sklearn or model imports. CSV joins use identifiers;
denoising truth is addressed by image/row/column, not the production row ordering.
Only the existing public-training-derived D_search references are permitted.
This verifies metric receipts, not final selection, test generalization or policy.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

BASE = Path('/research/d7/spc/yzyang4')
ROOTS = {
    'selective': ('scheduling-selective-20261017-v1', '1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32'),
    'quota': ('scheduling-generation-quota-20261017-v1', 'f08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9'),
}
TASKS = ('aerial-cactus-identification', 'denoising-dirty-documents')
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''): h.update(b)
    return h.hexdigest()


def read(p):
    b = Path(p).read_bytes()
    if SECRET.search(b): raise ValueError('credential-shaped metadata refused')
    return json.loads(b)


def rows(p, header):
    with Path(p).open(newline='') as f:
        r = csv.reader(f)
        if next(r) != header: raise ValueError('header')
        for row in r:
            if len(row) != len(header): raise ValueError('row width')
            yield row


def probability(x):
    x = float(x)
    if not math.isfinite(x) or not 0 <= x <= 1: raise ValueError('probability')
    return x


def auc_pairs(pairs):
    """Exact Mann-Whitney concordance with half credit for tied predictions."""
    pairs = sorted(pairs)
    if any(y not in (0, 1) for _, y in pairs): raise ValueError('binary truth')
    pos = sum(y for _, y in pairs); neg = len(pairs) - pos
    if not pos or not neg: raise ValueError('both classes required')
    negative_before = twice_concordant = i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][0] == pairs[i][0]: j += 1
        gp = sum(y for _, y in pairs[i:j]); gn = j - i - gp
        twice_concordant += gp * (2 * negative_before + gn)
        negative_before += gn; i = j
    return twice_concordant / (2 * pos * neg)


def aerial(reference, submission):
    truth = {}
    for ident, y in rows(reference, ['id', 'has_cactus']):
        if ident in truth or y not in ('0', '1'): raise ValueError('truth schema')
        truth[ident] = int(y)
    seen = set(); pairs = []
    for ident, x in rows(submission, ['id', 'has_cactus']):
        if ident not in truth or ident in seen: raise ValueError('ID coverage')
        seen.add(ident); pairs.append((probability(x), truth[ident]))
    if seen != set(truth): raise ValueError('missing ID')
    return auc_pairs(pairs), len(pairs)


def denoise(images, submission):
    # images maps canonical image number -> (width, height, raw grayscale bytes).
    coverage = {k: bytearray(w*h) for k, (w, h, _) in images.items()}
    expected = sum(w*h for w, h, _ in images.values()); count = 0
    def errors():
        nonlocal count
        for ident, value in rows(submission, ['id', 'value']):
            match = re.fullmatch(r'(0|[1-9][0-9]*)_([1-9][0-9]*)_([1-9][0-9]*)', ident)
            if not match or match[1] not in images: raise ValueError('pixel ID')
            key, y, x = match[1], int(match[2]), int(match[3])
            w, h, pixels = images[key]
            if not (1 <= x <= w and 1 <= y <= h): raise ValueError('pixel bounds')
            at = (y-1)*w+x-1
            if coverage[key][at]: raise ValueError('duplicate pixel')
            coverage[key][at] = 1; count += 1
            yield (probability(value)-pixels[at]/255.0)**2
    squared = math.fsum(errors())
    if count != expected: raise ValueError('missing pixel')
    return math.sqrt(squared/expected), count


def verify(name):
    from PIL import Image
    rel, pin = ROOTS[name]; root = BASE/rel
    if not (root/'closed.json').is_file(): raise ValueError('batch not closed')
    if sha(root/'plan.json') != pin: raise ValueError('plan drift')
    plan = read(root/'plan.json'); summary = read(root/'readout-20261017-v1/summary.json')
    if summary['assigned'] != 32 or summary['plan_sha256'] != pin: raise ValueError('wrong readout')
    spec = read(root/'dev-views/spec.json'); refs = {}; manifest_hashes = {}
    for task in TASKS:
        view = Path(spec[task]['view'])
        if not view.is_absolute(): view = root/view
        view = view.resolve()
        if view != (root/'dev-views'/task).resolve(): raise ValueError('unapproved view')
        manifest = view/'manifest.json'
        if sha(manifest) != spec[task]['view_sha']: raise ValueError('manifest drift')
        m = read(manifest)
        if not (m['not_official_test'] and m['not_confirmation'] and m['reserved_content_not_copied']): raise ValueError('scope')
        if m['split_seed'] != 'r14-image-dev-20261011': raise ValueError('split')
        query = m['query_ids']
        if len(query) != len(set(query)) or set(query)&set(m['train_ids']) or set(query)&set(m['reserved_ids']): raise ValueError('split overlap')
        expected_names = {'labels.csv'} if task == TASKS[0] else set(query)
        if set(m['search_reference_files']) != expected_names: raise ValueError('reference names')
        for n, h in m['search_reference_files'].items():
            if Path(n).name != n or sha(view/'search-reference'/n) != h: raise ValueError('reference drift')
        manifest_hashes[task] = sha(manifest)
        if task == TASKS[0]:
            refs[task] = view/'search-reference/labels.csv'
            ids = [r[0] for r in rows(refs[task], ['id', 'has_cactus'])]
            if len(ids) != len(set(ids)) or set(ids) != set(query): raise ValueError('query IDs')
        else:
            refs[task] = {}
            for n in query:
                key = str(int(Path(n).stem))
                if key in refs[task]: raise ValueError('image alias')
                with Image.open(view/'search-reference'/n) as image:
                    if list(image.size) != m['query_dimensions'][n]: raise ValueError('dimensions')
                    gray = image.convert('L'); refs[task][key] = (*gray.size, gray.tobytes())
    verified = []; maximum = 0.0
    for assignment in plan['schedule']:
        i, task = assignment['index'], assignment['task']; ep = root/f'episode-{i}'
        for f in sorted(ep.glob('scored-*.json')):
            if not re.fullmatch(r'scored-[0-9]+\.json', f.name): raise ValueError('score filename')
            receipt = read(f)['receipt']; submission = ep/(f.stem+'.private.csv')
            digest = sha(submission)
            if digest != receipt['submission_sha256']: raise ValueError('submission drift')
            if receipt.get('split') != 'D_search_development_only' or receipt['view_manifest_sha256'] != manifest_hashes[task]: raise ValueError('receipt scope')
            value, count = aerial(refs[task], submission) if task == TASKS[0] else denoise(refs[task], submission)
            field = 'auc' if task == TASKS[0] else 'rmse'; delta = abs(value-receipt[field])
            if count != receipt['rows'] or delta > 1e-12: raise ValueError('metric mismatch')
            maximum = max(maximum, delta)
            verified.append(dict(index=i, task=task, receipt=f.name, rows=count, metric=field,
                absolute_difference=delta, submission_sha256=digest, receipt_sha256=sha(f)))
    if len(verified) != summary['scores_recomputed']: raise ValueError('score denominator')
    return dict(schema=1, batch=name, plan_sha256=pin, source_commit=plan['source_commit'],
        implementation_sha256=sha(__file__), summary_sha256=sha(root/'readout-20261017-v1/summary.json'),
        view_manifest_sha256=manifest_hashes, verified_receipts=len(verified), maximum_absolute_difference=maximum,
        passed=True, records=verified, limits=['Independent metric computation, not independent source-data creation.',
        'Includes all stored scoring artifacts, not an eligibility or late-result rule.',
        'No official test, reserved split, model call, GPU, training, or original artifact modification.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('batch', choices=ROOTS)
    args = parser.parse_args(); print(json.dumps(verify(args.batch), sort_keys=True, allow_nan=False))
