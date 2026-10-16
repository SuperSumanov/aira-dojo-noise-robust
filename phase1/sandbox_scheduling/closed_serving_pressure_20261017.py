"""Read closed18807 service telemetry only; no model, scorer or new policy.

Application permit occupancy alone is not model-server saturation. Parse only
numeric telemetry after scanning/redacting credentials; never export raw logs.
These observational samples cannot estimate the effect of raising concurrency.
"""
import collections
import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
PLAN='36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560'
SUMMARY='c8c2f71009a39e9932ec59e388f9b052ce190730179119aed5d73e4fa38576a4'
SECRET=re.compile(r'(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|bearer\s+[A-Za-z0-9._-]{12,}|(?:api[_-]?key|token|secret|password)\s*[=:]\s*[\"\']?[A-Za-z0-9._-]{12,})')
NUMBER=r'(\d+(?:\.\d+)?)'
PATTERNS={
 'prompt_tokens_per_second':rf'Avg prompt throughput:\s*{NUMBER}',
 'generation_tokens_per_second':rf'Avg generation throughput:\s*{NUMBER}',
 'running_requests':rf'Running:\s*{NUMBER}',
 'waiting_requests':rf'Waiting:\s*{NUMBER}',
 'kv_cache_percent':rf'(?:GPU KV cache usage|KV cache usage):\s*{NUMBER}',
 'prefix_hit_percent':rf'(?:Prefix cache hit rate|GPU Prefix cache hit rate):\s*{NUMBER}',
}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def extract(text):
    safe,hits=SECRET.subn('[REDACTED]',text)
    samples=[]
    for line in safe.splitlines():
        if 'Avg generation throughput:' not in line:continue
        values={}
        for k,p in PATTERNS.items():
            m=re.search(p,line)
            if m:values[k]=float(m.group(1))
        if values:samples.append(values)
    return samples,hits

def main():
    assert digest((ROOT/'plan.json').read_bytes())==PLAN
    sp=ROOT/'readout-20261016-v1/summary.json'
    assert digest(sp.read_bytes())==SUMMARY and json.loads(sp.read_text())['complete']==32
    log=ROOT/'block-0/service.private.log';assert log.stat().st_size<32*1024**2
    raw=log.read_bytes();samples,hits=extract(raw.decode(errors='replace'))
    groups=collections.defaultdict(list)
    for s in samples:
        if 'running_requests' in s:groups[int(s['running_requests'])].append(s)
    def stats(rows):
        out={'samples':len(rows)}
        for field in PATTERNS:
            v=[r[field] for r in rows if field in r]
            if v:out[field]={'count':len(v),'min':min(v),'median':statistics.median(v),'max':max(v)}
        return out
    result=dict(plan_sha256=PLAN,primary_summary_sha256=SUMMARY,log_sha256=digest(raw),log_bytes=len(raw),
        reader_sha256=digest(Path(__file__).read_bytes()),credential_matches_redacted=hits,
        overall=stats(samples),by_running_requests={str(k):stats(v) for k,v in sorted(groups.items())},
        boundary='Closed-batch vLLM telemetry samples, not integrated GPU utilization or a concurrency intervention. Running/Waiting are server-side and distinct from application permits. No candidate text, labels, predictions, keys or raw logs exported. No new GPU/model/scorer calls, no altered experiment gate.')
    target=ROOT/'serving-pressure-20261017-v1.safe.json'
    with target.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,allow_nan=False))

if __name__=='__main__':main()
