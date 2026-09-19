"""Inspect official grader implementation only, never read answer data."""
import hashlib,inspect,json,re
from pathlib import Path
from mlebench.registry import registry
comp=registry.set_data_dir(Path('/research/d7/spc/yzyang4/mle-bench-data')).get_competition('random-acts-of-pizza')
out=dict(competition_type=type(comp).__name__,fields=list(vars(comp)),answers_read=False)
grader=getattr(comp,'grader',None)
if grader is not None:
    source=inspect.getsource(grader.grade_fn);raw=source.encode()
    if re.search(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})',raw):raise ValueError('source security')
    out.update(grader_type=type(grader).__name__,grader_name=grader.name,source_sha256=hashlib.sha256(raw).hexdigest(),source=source)
print(json.dumps(out,indent=2))
