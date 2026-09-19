"""Read exact historical selection semantics, credential-redacted remotely."""
import hashlib,json,subprocess
from discover_comparison_20260919 import safe_text
from inspect_comparison_20260919 import BASE,ROOT

COMMIT='be9335348b569086ef9b0af36a15b13e61fec45c'
PATHS={
 'src/dojo/core/solvers/utils/journal.py':[(1,80),(175,260)],
 'src/dojo/solvers/fore_ts/fore_ts.py':[(1,125),(190,225)],
 'src/dojo/solvers/mcts/mcts.py':[(210,255),(435,478)],
}
out=[]
for path,ranges in PATHS.items():
    raw=subprocess.check_output(['git','-C',str(BASE/'aira-dojo'),'show',COMMIT+':'+path],stderr=subprocess.PIPE)
    text=safe_text(raw.decode());lines=text.splitlines()
    out.append({'commit':COMMIT,'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'text':text})
    print(path,flush=True)
    for lo,hi in ranges:
        print('\n'.join(f'{i+1}: {s}' for i,s in enumerate(lines) if lo<=i+1<=hi),flush=True)
with (ROOT/'source-semantics.redacted.json').open('x') as f:json.dump(out,f,indent=2)
