"""Bounded metadata-only inventory, no labels/predictions/checkpoints loaded."""
import datetime
import json
import os
from pathlib import Path
import re
import time

BASE=Path('/research/d7/spc/yzyang4')
NAMES=('scheduling-pooling-20261016-v3','scheduling-colocation-20261016-v1',
       'scheduling-selective-20261017-v1','scheduling-image-live-2plus4-20261011-v3')
PATTERN=re.compile(r'(oof|out.of.fold|valid.*pred|pred.*valid|train.*pred|pred.*train)',re.I)
SECRET=re.compile(r'(?i)(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,})')
EXT={'.npy','.npz','.csv','.parquet','.pkl','.pickle','.pt','.pth','.joblib'}

rows=[]
for name in NAMES:
    root=BASE/name
    count=checkpoint_count=excluded_search_csv=0
    found=[];started=time.monotonic();truncated=False
    for episode in sorted(root.glob('episode-*')):
        if not episode.is_dir() or episode.is_symlink():continue
        for directory,dirs,files in os.walk(episode,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(directory)/d).is_symlink()
                     and d not in ('dev-views','search-reference','private','reserved','test','.git')]
            for fname in files:
                count+=1
                if count>20000 or time.monotonic()-started>15:
                    truncated=True;break
                path=Path(directory)/fname
                if path.is_symlink() or path.suffix.lower() not in EXT:continue
                if fname.startswith('scored-') or fname.endswith('.private.csv'):
                    excluded_search_csv+=1;continue
                if path.suffix.lower() in ('.pt','.pth','.joblib','.pkl','.pickle'):checkpoint_count+=1
                rel=str(path.relative_to(root))
                if PATTERN.search(rel):
                    assert not SECRET.search(rel), 'credential-shaped path refused'
                    found.append(dict(relative_path=rel,bytes=path.stat().st_size))
                    assert len(found)<=100, 'too many candidates: do not dump'
            if truncated:break
        if truncated:break
    rows.append(dict(root=str(root),files_seen=count,scope_truncated=truncated,
                     checkpoint_filename_count=checkpoint_count,excluded_search_prediction_csv=excluded_search_csv,
                     named_train_or_validation_prediction_candidates=found,elapsed_seconds=time.monotonic()-started))
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),metadata_only=True,rows=rows,
         limits=['Only four closed owned episode trees; no symlink traversal, file content, labels, predictions or checkpoint loaded.',
                 'Filename candidates are NOT verified OOF/validation provenance. Zero matches does not prove files absent outside this scope.',
                 'No current quota root, protected cohorts, D_val or official test accessed; no GPU/API/model calls or new prediction generation.'])
path=Path(__file__).with_name('closed-train-prediction-inventory.safe.json')
with path.open('x') as f:json.dump(out,f,indent=2,sort_keys=True)
print(json.dumps(out,sort_keys=True))
