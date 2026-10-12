/* Independent arithmetic/CSV verifier: does not import Python readout code. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = process.argv[2];
const read = n => JSON.parse(fs.readFileSync(path.join(root,n),'utf8'));
const hash = n => crypto.createHash('sha256').update(fs.readFileSync(path.join(root,n))).digest('hex');
const s=read('summary.json'), rows=read('runs.json'), ids=read('identity.json');
const order=['greedy','pending_ucb','feedback_gate','feedback_gate','pending_ucb','greedy'];
const tasks=['aerial-cactus-identification','denoising-dirty-documents'];
function csvParse(text) {
  const records=[]; let row=[],cell='',quoted=false;
  for(let i=0;i<text.length;i++) {
    const c=text[i];
    if(c==='"') { if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted; }
    else if(c===','&&!quoted){row.push(cell);cell='';}
    else if(c==='\n'&&!quoted){row.push(cell.replace(/\r$/,''));records.push(row);row=[];cell='';}
    else cell+=c;
  }
  assert.equal(quoted,false);
  if(cell||row.length){row.push(cell);records.push(row);}
  return records;
}
const csv=csvParse(fs.readFileSync(path.join(root,'runs.csv'),'utf8'));
const header=csv.shift(); assert.equal(csv.length,48); assert.equal(rows.length,48);
const encode=v => v===null?'':typeof v==='boolean'?(v?'True':'False'):String(v);
rows.forEach((r,i)=>{
  assert.equal(r.index,i); assert.equal(r.block,Math.floor(i/8));
  assert.equal(r.lane,Math.floor((i%8)/2));
  assert.equal(r.task,tasks[i%2]); assert.equal(r.arm,order[r.block]);
  assert.equal(r.seed,212701+100*Math.floor(r.block/3)+2*r.lane+i%2);
  assert.equal(r.run_seconds,1020); assert.equal(r.pool_seconds,1180);
  assert.equal(r.source_commit,'53de94e3b2bf07b5a46a9c388efe40d7dfdff8d7');
  assert.equal(csv[i].length,header.length);
  header.forEach((k,j)=>assert.equal(csv[i][j],encode(r[k]),`CSV row${i}/${k}`));
  if(!r.started) assert.equal(r.score,null);
  else {assert(Number.isFinite(r.score));assert((i%2===0?1:-1)*(r.score-r.initial_score)>=-1e-12);}
});
assert.equal(rows.filter(r=>r.started).length,40);
assert.equal(rows.filter(r=>r.complete).length,39);
assert.deepEqual(rows.filter(r=>r.started&&!r.complete).map(r=>r.index),[34]);
assert.equal(s.assigned,48);assert.equal(s.started,40);assert.equal(s.complete,39);
assert.equal(s.predeclared_success_gate_met,false);assert.equal(s.structural_gate,false);
assert.equal(s.full_quality_comparison_available,false);
assert.equal(s.gpu_seconds,6067*6);assert.equal(s.gpu_hours,s.gpu_seconds/3600);
assert.equal(s.service_gpu_clean,true);
assert.equal(s.plan_sha256,'e6d41cd7b40598f349e7956d3daaf610d85c5e00170b4d358b9e5cfdaa9910ee');
assert.deepEqual(s.blocks.filter(b=>b.qualified).map(b=>b.block),[0,1,2,3]);
assert.equal(ids.length,5);
ids.forEach(v=>{assert(v.valid);assert.deepEqual(v.lanes,ids[0].lanes);assert.deepEqual([...v.service].sort(),[...ids[0].service].sort());});
const scores=new Map();
for(const b of s.blocks) for(const task of tasks) {
  const rr=rows.filter(r=>r.block===b.block&&r.task===task);
  const value=b.qualified?(task===tasks[0]?Math.max(...rr.map(r=>r.score)):Math.min(...rr.map(r=>r.score))):null;
  assert.equal(value,b.scores[task]);scores.set(`${b.block}/${task}`,value);
}
const contrasts=[];
for(let rep=0;rep<2;rep++) for(const task of tasks) for(const ref of order.slice(0,2)) {
  const bb=order.map((a,b)=>({a,b})).filter(v=>Math.floor(v.b/3)===rep);
  const bm=bb.find(v=>v.a==='feedback_gate').b,br=bb.find(v=>v.a===ref).b;
  const m=scores.get(`${bm}/${task}`),r=scores.get(`${br}/${task}`);
  const delta=m===null||r===null?null:(task===tasks[0]?1:-1)*(m-r);
  const expected=s.contrasts.find(v=>v.repeat===rep&&v.task===task&&v.reference===ref);
  assert.equal(expected.method_best,m);assert.equal(expected.reference_best,r);
  assert.equal(expected.oriented_delta,delta);assert.equal(expected.comparable,delta!==null);
  const margin=task===tasks[0]?-1e-12:.001;
  assert.equal(expected.meets_original_margin,delta===null?null:delta>=margin);
  contrasts.push({repeat:rep,task,reference:ref,method_best:m,reference_best:r,oriented_delta:delta});
}
assert.equal(contrasts.filter(c=>c.oriented_delta!==null).length,4);
const first=contrasts.filter(c=>c.repeat===0);
const firstPass=first.every(c=>c.oriented_delta>=(c.task===tasks[0]?-1e-12:.001));
assert.equal(firstPass,s.first_repeat_meets_quality_rule);
const median=vs=>{vs=[...vs].sort((a,b)=>a-b);const n=vs.length;return n%2?vs[(n-1)/2]:(vs[n/2-1]+vs[n/2])/2;};
const sd=vs=>{const m=vs.reduce((a,b)=>a+b)/vs.length;return Math.sqrt(vs.reduce((a,b)=>a+(b-m)**2,0)/(vs.length-1));};
const summaries={};
for(const arm of order.slice(0,3)) {
  summaries[arm]={};
  for(const task of tasks) {
    const vs=rows.filter(r=>r.arm===arm&&r.task===task&&r.block<4).map(r=>r.score);
    const v={n:vs.length,median:median(vs),sample_sd:sd(vs)};
    const original=s.qualified_run_summary[arm][task];
    for(const k of ['n','median','sample_sd'])assert(Math.abs(v[k]-original[k])<1e-12);
    summaries[arm][task]=v;
  }
}
const output={status:'passed',method:'Independent Node arithmetic and CSV parsing; no Python analysis helpers.',
  source_commit:s.source_commit,plan_sha256:s.plan_sha256,assigned:48,started:40,complete:39,failed:1,unstarted:8,
  complete_equal_budget_pools:[0,1,2,3],comparable_contrasts:4,missing_contrasts:4,csv_json_cell_parity:true,
  first_repeat_quality_rule:firstPass,original_success_gate:false,contrasts,qualified_run_summary:summaries,
  gpu_seconds:s.gpu_seconds,gpu_hours:s.gpu_hours,
  transfer_sha256:Object.fromEntries(['summary.json','runs.json','runs.csv','identity.json'].map(n=>[n,hash(n)])),
  limitation:'One whole-budget pool per reference. Correlated task/seed comparisons are not independent experimental repetitions. Partial second-reference pool excluded, never imputed.'};
fs.writeFileSync(path.join(root,'independent-verification.json'),JSON.stringify(output,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(output));
