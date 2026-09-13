"""Remote-only setup structure; suppress every assignment RHS and credentials."""
from pathlib import Path
import re
p=Path.home()/'env_setup.sh'
for line in p.read_text().splitlines():
    if re.match(r'\s*#',line) or not line.strip():continue
    line=re.sub(r'((?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=).*',r'\1[REDACTED_RHS]',line)
    line=re.sub(r'(?i)(?:sk-[A-Za-z0-9._-]{8,}|hf_[A-Za-z0-9]{8,}|Bearer\s+\S+|https?://\S+)','[REDACTED]',line)
    print(line)
