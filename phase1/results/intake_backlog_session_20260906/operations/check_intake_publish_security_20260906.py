"""Narrow triage of source-binding receipts named environment.txt, NOT env dumps.

Original generic filename checker stays unchanged. Every other restricted path
and every credential-shape/binary/oversize finding still refuses publication.
"""
import hashlib,json,re,subprocess
root='phase1/results/intake_backlog_session_20260906/'
allowed={root+x+'/environment.txt' for x in ['prior_anchor_catchup']+[f'delta-{i:03d}' for i in range(1,15)]}
fields={'control_commit':'2e59423736747f7d806d50a69fd1f312d4927c48',
    'protocol_sha256':'c0bda0893a0f8099d2bf8ae8cd13ae3eeded64dcc28845a142e0facaf7d7327e',
    'primary_sha256':'9d5c56b9da33effd1d56275cccbe939f02a9cd32adb39ad33c8eb04340da67ce',
    'grounded_sha256':'5d9ff8a80d40b2d59bb2060052ff4101a65547a37a1012b6b6c6a19f3488e854'}
paths=subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode().strip('\0').split('\0')
assert allowed.issubset(paths)
m=json.loads(subprocess.check_output(['git','show',':'+root+'manifest.json']))
patterns=[rb'(?i)(?<![A-Za-z0-9])sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}',rb'gh[pousr]_[A-Za-z0-9]{20,}',
    rb'github_pat_[A-Za-z0-9_]{20,}',rb'hf_[A-Za-z0-9]{20,}',rb'AKIA[A-Z0-9]{16}',rb'AIza[0-9A-Za-z_-]{30,}',
    rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',rb'(?i)Bearer[ \t]+[A-Za-z0-9._-]{20,}']
reviewed=[]
for path in paths:
    raw=subprocess.check_output(['git','show',':'+path])
    assert b'\0' not in raw and len(raw)<=1024*1024
    assert not any(re.search(p,raw) for p in patterns)
    if path in allowed:
        lines=raw.decode('ascii').splitlines();assert len(lines)==6
        pairs=[x.split('=') for x in lines];assert all(len(x)==2 for x in pairs)
        d=dict(pairs);assert set(d)==set(fields)|{'prior_snapshot','current_snapshot'}
        assert all(d[k]==v for k,v in fields.items())
        assert all(re.fullmatch('[0-9a-f]{64}',d[k]) for k in ('prior_snapshot','current_snapshot'))
        assert m[path[len(root):]]=={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        reviewed.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'six_hash_only_fields':True})
    else:
        assert not path.endswith('quarantined-uv.lock') and not re.search('env|key|token|secret',path,re.I)
print(json.dumps({'staged_files':len(paths),'credential_shape_hits':0,'known_filename_triage':reviewed,
    'generic_scanner_modified':False,'environment_variable_values_present':False},sort_keys=True))
