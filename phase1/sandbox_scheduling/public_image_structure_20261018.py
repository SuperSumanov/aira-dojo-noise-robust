"""Public TRAIN only: file-byte duplicate structure, no held-out label access."""
from collections import Counter
import hashlib,json
from pathlib import Path

B=Path('/research/d7/spc/yzyang4')
D=B/'scheduling-selective-20261017-v1'
s=json.loads((D/'dev-views/spec.json').read_text())
task='denoising-dirty-documents'
v=Path(s[task]['view']);m=json.loads((v/'manifest.json').read_text())
assert m['not_official_test'] and m['reserved_content_not_copied']
assert hashlib.sha256((v/'manifest.json').read_bytes()).hexdigest()==s[task]['view_sha']
p=v/'public'
out={'view':str(v),'manifest_sha256':s[task]['view_sha'],
     'public_top_names':sorted(x.name for x in p.iterdir()),'train_only':[]}
for dn in ('train','train_cleaned'):
    d=p/dn
    if not d.is_dir():continue
    hs=Counter();sizes=Counter()
    for f in sorted(d.glob('*.png')):
        assert f.is_file() and not f.is_symlink()
        raw=f.read_bytes();hs[hashlib.sha256(raw).hexdigest()]+=1
        assert raw[:8]==b'\x89PNG\r\n\x1a\n'
        sizes[(int.from_bytes(raw[16:20],'big'),int.from_bytes(raw[20:24],'big'))]+=1
    out['train_only'].append({'directory':dn,'n':sum(hs.values()),'byte_unique':len(hs),
                             'group_sizes':sorted(hs.values(),reverse=True),
                             'dimensions':[[*k,n] for k,n in sorted(sizes.items())]})
    if dn=='train_cleaned':
        # Existing allowed DEV reference checksums only; never open label pixels.
        q=list(m['search_reference_files'].values())
        out['dev_reference_metadata']={'n':len(q),'byte_hash_present_in_public_train':sum(h in hs for h in q),
                                       'unique_hashes':len(set(q))}
out['contract_requires_cuda_training']='Use a real PyTorch CUDA-trained model' in (p/'description.md').read_text()
out['limits']=['An overlap is a dataset dependency, not an observed prediction benefit.',
               'The old task contract requires CUDA training; CPU retrieval is only an out-of-contract diagnostic, not a legal arm beating R14.',
               'No reserved inputs, official test, or protected cohort accessed.']
print(json.dumps(out))
