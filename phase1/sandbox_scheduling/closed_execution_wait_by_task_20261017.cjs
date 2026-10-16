// Read-only decomposition of sealed, independently verified admission traces.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const dir=process.argv[2],names=['aerial-cactus-identification','denoising-dirty-documents'];
const summary=JSON.parse(fs.readFileSync(`${dir}/summary.json`)),out=[],hashes={};
const median=v=>{if(!v.length)return null;v.sort((a,b)=>a-b);return(v[Math.floor(v.length/2)]+v[Math.floor((v.length-1)/2)])/2;};
for(let b=0;b<4;b++){
 const name=`queue-${b}.json`,raw=fs.readFileSync(`${dir}/${name}`),events=JSON.parse(raw),pending=new Map(),seen=new Set();
 hashes[name]=crypto.createHash('sha256').update(raw).digest('hex');
 const g=names.map(task=>({block:b,mode:summary.queues[b].pool_mode,task,queued:0,admitted:0,cancelled:0,waits:[],cancelled_wait_seconds:0}));
 for(const e of events){
  const i=Number(e.key.split(':')[0]);assert.ok(Number.isInteger(i)&&Math.floor(i/8)===b);const r=g[i%2];
  if(e.event==='queued'){assert.ok(!seen.has(e.key));seen.add(e.key);pending.set(e.key,e.time);r.queued++;}
  else if(e.event==='admitted'||e.event==='queue_cancelled'){
   assert.ok(pending.has(e.key));const wait=e.time-pending.get(e.key);assert.ok(wait>=0);pending.delete(e.key);
   if(e.event==='admitted'){r.admitted++;r.waits.push(wait);}else{r.cancelled++;r.cancelled_wait_seconds+=wait;}
  }else assert.equal(e.event,'released');
 }
 assert.equal(pending.size,0);
 assert.equal(g.reduce((n,r)=>n+r.admitted,0),summary.queues[b].admissions);
 assert.ok(Math.abs(g.flatMap(r=>r.waits).reduce((a,b)=>a+b,0)-summary.queues[b].wait_total)<1e-9);
 for(const {waits,...r} of g){assert.equal(r.queued,r.admitted+r.cancelled);out.push({...r,
  admitted_wait_seconds:waits.reduce((a,b)=>a+b,0),wait_median:median(waits),wait_max:waits.length?Math.max(...waits):null});}
}
console.log(JSON.stringify({schema:1,summary_sha256:crypto.createHash('sha256').update(fs.readFileSync(`${dir}/summary.json`)).digest('hex'),hashes,rows:out,
 limitation:'Descriptive after closure, not a new quality gate or causal latency mediation. Sum includes concurrent requests, not wall time or GPU savings.'},null,2));
