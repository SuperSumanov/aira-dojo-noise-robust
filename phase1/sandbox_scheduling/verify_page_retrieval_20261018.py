"""Independent recomputation of sealed public-only controls; aggregates only.

Never imports the predictor. Uses its sealed files and the pre-existing allowed
DEV manifest. Does not alter frozen outputs or claim a legal R14 treatment.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '2'
import hashlib
import json
import math
import time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

B = Path('/research/d7/spc/yzyang4')
V = B/'scheduling-image-live-2plus4-20261011-v1/dev-views/denoising-dirty-documents'
P = V/'public'
O = B/'page-retrieval-diagnostic-20261018-v1'
MODES = ('clean_raw', 'clean_highpass', 'noisy_raw', 'noisy_highpass')
MANIFEST_SHA = '31698d35766aa5fc99ec2b56ee00cbcf21e994eeaf0ab59aaa1e9962a59c2acb'
SEAL_SHA = 'b79f227f277a2f06a7c387505f3e439b43332f66d57f8532ccacb2b5e582faba'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def pixels(p):
    with Image.open(p) as im: return np.array(im.convert('L'), dtype=np.uint8)

def correlation(a, b, hp):
    a, b = a.astype(float)/255, b.astype(float)/255
    if hp:
        a -= gaussian_filter(a, sigma=1.5, mode='reflect')
        b -= gaussian_filter(b, sigma=1.5, mode='reflect')
    a -= np.mean(a); b -= np.mean(b)
    return float(np.sum(a*b)/math.sqrt(float(np.sum(a*a)*np.sum(b*b))))

def main():
    start = time.monotonic()
    assert digest(V/'manifest.json') == MANIFEST_SHA
    assert digest(O/'prediction-seal.json') == SEAL_SHA
    m, seal, summary = read(V/'manifest.json'), read(O/'prediction-seal.json'), read(O/'summary.safe.json')
    assert m['not_official_test'] and m['reserved_content_not_copied']
    for name, sha in seal['files'].items(): assert digest(O/name) == sha
    for name, sha in seal['public_input_sha256'].items(): assert digest(P/name) == sha
    for name, sha in m['search_reference_files'].items(): assert digest(V/'search-reference'/name) == sha
    train = sorted((P/'train_cleaned').glob('*.png'))
    clean = {p.name: pixels(p) for p in train}
    noisy = {p.name: pixels(P/'train'/p.name) for p in train}
    selected = {(x['mode'], x['query']): x['train'] for x in read(O/'selection.private.json')}
    rows = []
    for mode in MODES:
        proto = clean if mode.startswith('clean') else noisy
        exact = integer_sse = count = 0
        with np.load(O/(mode+'.prediction.private.npz'), allow_pickle=False) as preds:
            assert set(preds.files) == set(m['query_ids'])
            for query in sorted(preds.files):
                x = pixels(P/'test'/query)
                scores = [(correlation(x, a, 'highpass' in mode), n)
                          for n, a in proto.items() if a.shape == x.shape]
                # Max in stable name order: same explicit tie convention, separate implementation.
                name = max(scores, key=lambda pair: pair[0])[1]
                assert name == selected[mode, query]
                assert np.array_equal(preds[query], clean[name])
                target = pixels(V/'search-reference'/query)
                d = target.astype(np.int64)-preds[query].astype(np.int64)
                integer_sse += int(np.sum(d*d, dtype=np.int64)); count += d.size
                exact += int(not np.any(d))
        rmse = math.sqrt(integer_sse/count)/255
        original = next(x for x in summary['groups'] if x['mode'] == mode)
        assert abs(rmse-original['rmse']) < 1e-12 and exact == original['exact_images']
        rows.append(dict(mode=mode, images=len(m['query_ids']), exact_images=exact, rmse=rmse,
                         integer_sse=integer_sse, pixels=int(count)))
    hashes = {digest(p) for p in train}
    result = dict(status='INDEPENDENT_PUBLIC_SELECTION_AND_DEV_SCORE_VERIFIED', groups=rows,
                  manifest_sha256=MANIFEST_SHA, prediction_seal_sha256=SEAL_SHA,
                  verifier_sha256=digest(Path(__file__)), summary_sha256=digest(O/'summary.safe.json'),
                  public_clean_images=len(train), public_clean_unique_bytes=len(hashes),
                  dev_reference_matches=sum(h in hashes for h in m['search_reference_files'].values()),
                  old_cuda_requirement='Use a real PyTorch CUDA-trained model' in (P/'description.md').read_text(),
                  seconds=time.monotonic()-start, gpu_seconds=0, paid_api=0,
                  limits=['Not a legal R14 arm or unseen-page generalization test.',
                          'Independent algorithm/score recomputation, not independent data or seeds.'])
    with (O/'independent.safe.json').open('x') as f: json.dump(result, f, indent=2, allow_nan=False)
    print(json.dumps(result))

if __name__ == '__main__': main()
