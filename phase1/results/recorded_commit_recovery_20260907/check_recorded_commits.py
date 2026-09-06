"""Read only hash-bound historical provenance and Git code metadata, no journals."""
import ast,collections,datetime,hashlib,json,re,subprocess
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
INPUTS={
 'ledger':('historical-source-ledger-faf04cc-20260905/source_ledger.private.json','8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'),
 'scope':('historical-runtime-prefix-79164e0-20260906-A/runtime_prefix.private.json','fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b')}
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(name):
 path,digest=INPUTS[name];raw=(BASE/path).read_bytes()
 assert sha(raw)==digest and not SECRET.search(raw)
 return json.loads(raw)
def git(repo,*args):
 p=subprocess.run(['git','-C',str(repo),*args],capture_output=True,timeout=30)
 assert not SECRET.search(p.stdout+p.stderr)
 return p
ledger,scope=load('ledger'),load('scope');selected=set(scope['selected_runs'])
assert len(ledger)==676 and len(selected)==84 and selected<=set(ledger)
all_counts=collections.Counter();selected_counts=collections.Counter()
for rid,row in ledger.items():
 commits={r['recorded_runner_git_commit'] for r in row['origins']}
 assert len(commits)==1
 commit=commits.pop();assert re.fullmatch('[0-9a-f]{40}',commit)
 all_counts[commit]+=1
 if rid in selected:selected_counts[commit]+=1
rows=[];repo=BASE/'aira-dojo-reproduce'
for commit,count in sorted(all_counts.items()):
 exists=git(repo,'cat-file','-e',commit+'^{commit}').returncode==0
 row={'commit':commit,'historical_runs':count,'fixed_84_runs':selected_counts[commit],'git_commit_readable':exists}
 if exists:
  tree=git(repo,'rev-parse',commit+'^{tree}');assert tree.returncode==0
  row['git_tree']=tree.stdout.decode().strip()
  inventory=git(repo,'ls-tree','-r',commit);assert inventory.returncode==0
  row['tree_inventory_sha256']=sha(inventory.stdout)
  row['tracked_blob_count']=sum(b' blob ' in line for line in inventory.stdout.splitlines())
  row['gitlinks']=sum(line.startswith(b'160000 ') for line in inventory.stdout.splitlines())
  resolver=git(repo,'show',commit+':src/dojo/config_dataclasses/omegaconf/resolvers.py')
  assert resolver.returncode==0
  node=next(n for n in ast.parse(resolver.stdout).body if isinstance(n,ast.FunctionDef) and n.name=='get_git_commit_id')
  row['resolver_blob_sha256']=sha(resolver.stdout)
  row['resolver_body']=ast.unparse(node)
 rows.append(row)
result={'classification':'RECORDED_GIT_CODE_RECOVERABILITY_NOT_RUNTIME_OR_TRAINING_ADMISSION',
 'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'script_sha256':sha(Path(__file__).read_bytes()),
 'input_sha256':{k:v[1] for k,v in INPUTS.items()},'historical_runs':len(ledger),'fixed_scope_runs':len(selected),
 'recorded_commits':len(all_counts),'readable_commits':sum(r['git_commit_readable'] for r in rows),
 'fixed_scope_commits':len(selected_counts),'fixed_scope_runs_with_readable_commit':sum(r['fixed_84_runs'] for r in rows if r['git_commit_readable']),
 'records':rows,'snapshot_required_to_read_committed_code':False,'uncommitted_changes_attested':False,
 'installed_evaluator_attested':False,'new_source_admission':False,'journal_or_outcome_payload_reads':0,'protected_cohort_reads':0}
assert not SECRET.search(json.dumps(result).encode())
path=BASE/'recorded-commit-recovery-20260907.json'
with path.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
