"""Read-only source contract inspection for the one frozen public XGB program."""
import ast
import json
import re
from pathlib import Path
from lifecycle_pilot import SECRET,sha

p=Path('/research/d7/spc/yzyang4/scheduling-pool-20261008-v1/programs/0.py')
expected='c7bc94f0237d85aaf1c89ad9f9630f34f71b7c134551095a3f02992172e08e5b'
raw=p.read_bytes()
if sha(p)!=expected or SECRET.search(raw):raise ValueError('untrusted source')
source=raw.decode();ast.parse(source);lines=source.splitlines();selected=set()
for i,line in enumerate(lines):
 if re.search(r'label|class|mapping|unique|train_test_split|\.fit\(|mask|drop|filter|target',line,re.I):
  selected.update(range(max(0,i-2),min(len(lines),i+3)))
print(json.dumps(dict(source_sha256=expected,source_lines=[dict(line=i+1,text=lines[i]) for i in sorted(selected)],
                     no_execution=True,no_scores_read=True),sort_keys=True))
