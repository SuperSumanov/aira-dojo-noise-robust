"""Read-only allowlisted status for the two fixed evening roots."""
import json
from pathlib import Path
from lifecycle_pilot import read, sha

B = Path('/research/d7/spc/yzyang4')
result = {}
for suffix in ('readiness-live-20261008-evening-v1','neural-qualified-overlap-20261008-evening-v1'):
    root = B/('scheduling-'+suffix)
    item = {'exists':root.exists()}
    for name in ('launch','preflight','closed'):
        path = root/(name+'.json')
        if path.exists():
            item[name] = read(path)
    if (root/'plan.json').exists():
        item['plan_sha256'] = sha(root/'plan.json')
    episodes = []
    for ep in sorted(root.glob('episode-*')):
        row = {'index':int(ep.name.removeprefix('episode-'))}
        for name in ('started','candidate_started','candidate_ended'):
            row[name] = (ep/(name+'.json')).exists()
        for name in ('closed','completed'):
            path = ep/(name+'.json')
            if path.exists():
                obj = read(path)
                row[name] = {k:obj[k] for k in ('returncode','complete','error_type','elapsed_seconds','timed_out','exec_seconds') if k in obj}
        path = ep/'handshake.json'
        if path.exists():
            row['handshake'] = read(path)
        if 'closed' in row or 'completed' in row or row['started']:
            episodes.append(row)
    item['episodes'] = episodes
    result[suffix] = item
print(json.dumps(result, sort_keys=True))
