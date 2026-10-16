// Read-only descriptive bridge from model-call counts to timely result yield.
// No performance threshold, candidate selection, or causal mediation estimate.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const dir=process.argv[2];assert.ok(dir,'closed readout directory required');
const hashes={};
const read=n=>{const b=fs.readFileSync(`${dir}/${n}`);hashes[n]=crypto.createHash('sha256').update(b).digest('hex');return JSON.parse(b);};
const runs=read('runs.json'),effort=read('effort.json'),summary=read('summary.json');
assert.equal(runs.length,summary.assigned);assert.equal(new Set(runs.map(r=>r.index)).size,runs.length);
assert.equal(summary.complete,runs.filter(r=>r.complete).length);
const known=new Set(runs.map(r=>r.index));
for(const e of effort){assert.ok(known.has(e.index));assert.ok(['draft','improve','debug','analyze'].includes(e.role));assert.ok(Number.isFinite(e.seconds)&&e.seconds>=0);}
const rows=[];
for(const block of [...new Set(runs.map(r=>r.block))].sort((a,b)=>a-b))for(const task of [...new Set(runs.map(r=>r.task))].sort()){
 const r=runs.filter(r=>r.block===block&&r.task===task),ids=new Set(r.map(r=>r.index));assert.equal(r.length,4);
 const e=effort.filter(e=>ids.has(e.index));const roles=Object.fromEntries(['draft','improve','debug','analyze'].map(k=>[k,e.filter(x=>x.role===k).length]));
 const signed=task==='denoising-dirty-documents'?-1:1;
 assert.ok(r.every(x=>x.initial_score===r[0].initial_score));
 const stat=summary.by_pool.find(x=>x.block===block&&x.task===task);assert.ok(stat);
 const tokens=e.filter(x=>Number.isFinite(x.usage?.completion_tokens));
 rows.push({block,task,pool_mode:r[0].pool_mode,quota_mode:r[0].quota_mode??null,assigned:r.length,
  complete:r.filter(x=>x.complete).length,calls:e.length,successful_calls:e.filter(x=>x.success).length,
  unsuccessful_calls:e.filter(x=>!x.success).length,roles,
  request_seconds:e.reduce((s,x)=>s+x.seconds,0),reported_completion_tokens:tokens.reduce((s,x)=>s+x.usage.completion_tokens,0),
  calls_missing_completion_tokens:e.length-tokens.length,
  timely_candidate_returns:r.reduce((s,x)=>s+x.candidate_returns,0),timely_valid_returns:r.reduce((s,x)=>s+x.valid_returns,0),
  own_trajectories_improving_warm:r.filter(x=>signed*(x.score-x.initial_score)>0).length,
  initial_score:r[0].initial_score,pool_best:stat.best,oriented_best_gain:signed*(stat.best-r[0].initial_score)});
}
assert.equal(rows.reduce((s,x)=>s+x.calls,0),effort.length);
console.log(JSON.stringify({schema:1,hashes,rows,limits:[
 'Descriptive after closure, not a changed gate or causal effect of debug calls.',
 'Improve role does not certify a new scientific hypothesis; debug may itself improve quality.',
 'Request durations overlap and are not wall-time or GPU savings.',
 'Tokens are reported usage only; interrupted requests may lack usage and are counted as missing.',
 'Timely returns differ from all pristine rescores; warm and peer archive use remain in the original protocol.',
 'Four trajectories share a task archive; they are not four independent treatment replications.'
]},null,2));
