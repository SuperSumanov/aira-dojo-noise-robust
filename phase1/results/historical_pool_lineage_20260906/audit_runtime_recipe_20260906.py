import collections,hashlib,json,re,subprocess,sys
from pathlib import Path
root=Path('/research/d7/spc/yzyang4');repo=str(root/'aira-dojo-reproduce')
raw=(root/'historical-source-ledger-faf04cc-20260905/source_ledger.private.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'
commits=sorted({r['origins'][0]['recorded_runner_git_commit'] for r in json.loads(raw).values()})
missing=[];recipe=collections.Counter();pins=set();retrieval=[]
shape=re.compile(rb'(?i)(?:sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9_.-]{20,})')
for commit in commits:
 assert re.fullmatch('[0-9a-f]{40}',commit)
 if subprocess.run(['git','-C',repo,'cat-file','-e',commit+'^{commit}'],capture_output=True).returncode:
  try:
   attempt=subprocess.run(['git','-C',repo,'fetch','--no-tags','fork',commit],capture_output=True,timeout=30)
   retrieval.append({'recorded_commit':commit,'fetch_returncode':attempt.returncode})
  except subprocess.TimeoutExpired:retrieval.append({'recorded_commit':commit,'fetch_returncode':'timeout'})
 if subprocess.run(['git','-C',repo,'cat-file','-e',commit+'^{commit}'],capture_output=True).returncode:
  missing.append(commit);continue
 path='src/dojo/tasks/mlebench/README.md'
 doc=subprocess.check_output(['git','-C',repo,'show',commit+':'+path]);assert not shape.search(doc)
 recipe[hashlib.sha256(doc).hexdigest()]+=1
 pins.update(x.decode() for x in re.findall(rb'(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])',doc))
result={'status':'DOCUMENTED_INSTALL_RECIPE_NOT_RUNTIME_ATTESTATION','recorded_commits':len(commits),
        'readable_recorded_commits':len(commits)-len(missing),'missing_recorded_commits':missing,
        'exact_commit_fetch_attempts':retrieval,'readme_sha256_counts':dict(recipe),'documented_pins':sorted(pins),
        'actual_installed_evaluator_version_attested':False,'runtime_pristine_attested':False,
        'protected_cohort_or_result_payload_reads':0,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out=root/'historical-runtime-recipe-20260906.json'
with out.open('x') as f:json.dump(result,f,sort_keys=True);f.write('\n')
out.chmod(0o400);print(json.dumps(result,sort_keys=True))
