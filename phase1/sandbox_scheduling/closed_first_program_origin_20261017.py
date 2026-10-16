"""Check that closed18997 first-program hashes are native journal programs.

This excludes common wrapper instrumentation as the source of hash inequality
only when the exact native journal code matches. Unknowns are not discarded.
"""
import hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/scheduling-selective-20261017-v1')
PIN='b87aa52b18e0e06b02e888bd988bca2c6b9ba4c7e454f3da9829119fad0fab3e'
SECRET=re.compile(r'(?i)sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,}')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 f=R/'first-program-pairing-20261017.safe.json';assert sha(f)==PIN and (R/'closed.json').exists()
 receipt=read(f);rows=[]
 for r in receipt['rows']:
  ep=R/f"episode-{r['index']}";jp=ep/'checkpoint/journal.jsonl';raw=jp.read_text()
  assert not SECRET.search(raw),'credential-shape hit; no export'
  nodes=[json.loads(line) for line in raw.splitlines() if line.strip()]
  matches=[n for n in nodes if isinstance(n.get('code'),str) and hashlib.sha256(n['code'].encode()).hexdigest()==r['code_sha256']]
  roles=sorted({role for n in matches for role in n.get('operators_used',[]) if role in ('draft','improve','debug','crossover')})
  efforts=[json.loads(line) for line in (ep/'effort.jsonl').read_text().splitlines() if line.strip()]
  code_calls=[e for e in efforts if e.get('role') in ('draft','improve','debug','crossover')]
  first=code_calls[0] if code_calls else {}
  rows.append(dict(index=r['index'],task=r['task'],journal_sha256=sha(jp),native_code_matches=len(matches),roles=roles,
   first_logged_code_role=first.get('role'),first_logged_code_success=first.get('success'),
   first_logged_code_adapter_attempts=first.get('usage',{}).get('adapter_attempts')))
 out=dict(parent_sha256=PIN,reader_sha256=sha(Path(__file__)),assigned=len(rows),rows=rows,
  native_code_matched=sum(r['native_code_matches']>0 for r in rows),
  native_improve_only=sum(r['roles']==['improve'] for r in rows),
  first_logged_code_successful_improve=sum(r['first_logged_code_role']=='improve' and r['first_logged_code_success'] is True for r in rows),
  boundary='Native-code hash association, not independent extraction of model transport responses or attribution to dynamic batching. Native journal membership excludes an execution-only wrapper as the matched code source. First logged successful call is not proof of server-side determinism or exact request handling.')
 dest=R/'first-program-origin-20261017.safe.json'
 with dest.open('x') as h:json.dump(out,h,indent=2,allow_nan=False)
 print(json.dumps({k:v for k,v in out.items() if k!='rows'}|dict(sha256=sha(dest))))
if __name__=='__main__':main()
