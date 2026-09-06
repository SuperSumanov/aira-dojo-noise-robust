import hashlib,json,re,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
src=Path('tmp/frozen-native-accepted-f5b3');out=Path('phase1/results/frozen_native_wire_20260906')
assert not out.exists()
names=['SUMMARY.json','child_receipt.json','SOURCE_MANIFEST.json','stdout.log','stderr.log','junit.xml']
raw={n:(src/n).read_bytes() for n in names}
pattern=rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})'
assert all(not re.search(pattern,b) for b in raw.values())
s=json.loads(raw['SUMMARY.json']);c=json.loads(raw['child_receipt.json']);sources=json.loads(raw['SOURCE_MANIFEST.json'])
commit='f5b3f6f4e262e19f0045d15957f93d8223d03af2'
assert s['commit']==commit and s['returncode']==0 and s['source_unchanged'] is True and len(sources)==s['source_files']==210
assert s['archive_sha256']=='84504067830fa7413fb9165632f908f2bf4cdb75e2b8842b0fe619c503fbf2ba'
assert c['pytest_rc']==0 and c['network_attempts']==[] and c['protected_path_attempt_hashes']==[]
assert c['real_api_calls']==c['real_mle_executions']==0 and c['source_or_effect_qualification'] is False
for n in ['stdout','stderr']:assert hashlib.sha256(raw[n+'.log']).hexdigest()==s[n+'_sha256']
for path,row in sources.items():
 b=subprocess.check_output(['git','show',commit+':'+path])
 assert row=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
xml=ET.fromstring(raw['junit.xml']);suites=list(xml.iter('testsuite'))
assert len(suites)==1 and suites[0].get('tests')=='34' and suites[0].get('failures')=='0' and suites[0].get('errors')=='0' and suites[0].get('skipped')=='0'
out.mkdir()
for n,b in raw.items():
 with (out/n).open('xb') as f:f.write(b)
inventory={n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in raw.items()}
with (out/'MANIFEST.json').open('x') as f:json.dump(inventory,f,sort_keys=True,indent=2)
print(json.dumps({'verified_tests':34,'verified_source_files':len(sources),'verified_receipt_files':len(raw),
 'network_attempts':0,'protected_path_attempts':0,'real_api_calls':0,'model_effect_measured':False}))
