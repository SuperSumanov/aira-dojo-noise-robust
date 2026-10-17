'use strict';
const fs=require('node:fs'), crypto=require('node:crypto'), assert=require('node:assert/strict');
const [input,source,output]=process.argv.slice(2);
const digest=x=>crypto.createHash('sha256').update(x).digest('hex');
const raw=fs.readFileSync(input), d=JSON.parse(raw);
assert.equal(digest(raw),'9339b98d853488e7787238e31d36b2eac033c7e40a0dbf58d6f4f2b1e1eeef71');
assert.equal(digest(fs.readFileSync(source)),d.reader_sha256);
assert.deepEqual(d.pools.map(x=>x.job),['18807','18997','19004']);
const result=[];
for(const p of d.pools){
  assert.equal(p.unparsed_metric_lines,0); assert.equal(p.gaps.length,4);
  assert([0,28800].includes(p.inferred_log_utc_offset_seconds));
  for(const g of p.gaps){
    assert(g.last_client_release<=g.slot_end && g.slot_end<=g.interval_end);
    assert.equal(g.next_first_queue,g.block<3?g.interval_end:null);
    let zero=0,busy=0,previous=-Infinity;
    for(const s of g.samples){
      assert(s.seconds_after_last_release>0 && s.seconds_after_last_release<g.interval_end-g.last_client_release);
      assert(s.seconds_after_last_release>=previous); previous=s.seconds_after_last_release;
      assert(Number.isInteger(s.running)&&s.running>=0&&Number.isInteger(s.waiting)&&s.waiting>=0);
      if(s.running===0 && s.waiting===0) zero++; else busy++;
    }
    assert.equal(zero,g.observed_zero_samples); assert.equal(busy,g.observed_busy_samples);
    result.push({job:p.job,block:g.block,gap_seconds:g.interval_end-g.last_client_release,samples:g.samples.length,zero,busy});
  }
}
const out={passed:true,receipt_sha256:digest(raw),verifier_sha256:digest(fs.readFileSync(__filename)),
  telemetry_samples:d.pools.reduce((n,p)=>n+p.telemetry_samples,0),gaps:result.length,
  zero_samples:result.reduce((n,x)=>n+x.zero,0),busy_samples:result.reduce((n,x)=>n+x.busy,0),by_gap:result,
  limits:['Independent arithmetic/source/transfer verification, not a second extraction of private service logs.',
    'All sampled gaps idle does not prove continuous idle, request-ID cancellation, cache neutrality or causal quality effects.',
    'No change to sealed primary readouts or invalid19004 status.']};
fs.writeFileSync(output,JSON.stringify(out,null,2)+'\n',{flag:'wx'}); console.log(JSON.stringify(out));
