// Independent final-quality/queue replay. Does not execute the Python reader.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const TASKS=['aerial-cactus-identification','denoising-dirty-documents'];
const ORDER=['fixed','shared','shared','fixed'];
const close=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-12);
const sha=raw=>crypto.createHash('sha256').update(raw).digest('hex');
function summarize(rows){
 const out=[];
 for(let block=0;block<4;block++)for(const task of TASKS){
  const v=rows.filter(r=>r.block===block&&r.task===task).map(r=>r.score).sort((a,b)=>a-b);
  assert.equal(v.length,4);assert.ok(v.every(Number.isFinite));const mean=v.reduce((a,b)=>a+b,0)/4;
  out.push({block,repeat:Math.floor(block/2),pool_mode:ORDER[block],task,best:task===TASKS[0]?v[3]:v[0],
   median:(v[1]+v[2])/2,sample_sd:Math.sqrt(v.reduce((a,x)=>a+(x-mean)**2,0)/3),n:4});
 }
 return out;
}
function contrast(by){
 const out=[];
 for(let repeat=0;repeat<2;repeat++)for(const task of TASKS){
  const a=by.find(r=>r.repeat===repeat&&r.task===task&&r.pool_mode==='fixed');
  const b=by.find(r=>r.repeat===repeat&&r.task===task&&r.pool_mode==='shared');
  const sign=task===TASKS[0]?1:-1;
  out.push({repeat,task,fixed_best:a.best,shared_best:b.best,oriented_delta:sign*(b.best-a.best),median_delta:sign*(b.median-a.median)});
 }
 return out;
}
function queue(events,mode){
 const pending=[],active=Array(4).fill(null),seen=new Set(),submitted=new Map(),waits=[];let migrations=0,last=-Infinity;
 for(const e of events){
  assert.ok(e.time>=last);last=e.time;
  if(e.event==='queued'){
   assert.ok(!seen.has(e.key));seen.add(e.key);pending.push({key:e.key,home:e.home});submitted.set(e.key,e.time);
  }else if(e.event==='admitted'){
   const at=mode==='shared'?0:pending.findIndex(x=>x.home===e.device);
   assert.ok(at>=0);const r=pending[at];assert.equal(r.key,e.key);assert.equal(active[e.device],null);
   if(mode==='fixed')assert.equal(e.device,r.home);else assert.equal(e.device,active.findIndex(x=>x===null));
   pending.splice(at,1);active[e.device]=e.key;migrations+=e.device!==r.home;waits.push(e.time-submitted.get(e.key));
  }else if(e.event==='released'){assert.equal(active[e.device],e.key);active[e.device]=null;}
  else if(e.event==='queue_cancelled'){
   const at=pending.findIndex(x=>x.key===e.key);assert.ok(at>=0);pending.splice(at,1);
  }else throw Error('unknown queue event');
  assert.equal(e.active,active.filter(x=>x!==null).length);assert.equal(e.queued,pending.length);
 }
 assert.equal(pending.length,0);assert.ok(active.every(x=>x===null));waits.sort((a,b)=>a-b);
 return {admissions:waits.length,migrations,wait_total:waits.reduce((a,b)=>a+b,0),
  wait_median:waits.length?(waits[Math.floor(waits.length/2)]+waits[Math.floor((waits.length-1)/2)])/2:null};
}
function tests(){
 const rows=Array.from({length:32},(_,i)=>({block:Math.floor(i/8),task:TASKS[i%2],score:i%2?.02-(ORDER[Math.floor(i/8)]==='shared'?.002:0):.99}));
 const q=contrast(summarize(rows));assert.ok(q.every(r=>r.oriented_delta>=(r.task===TASKS[1]?.001:-1e-12)));
 rows[16].score=.90;rows[18].score=.90;rows[20].score=.90;rows[22].score=.90;
 assert.ok(contrast(summarize(rows)).some(r=>r.oriented_delta<0));assert.throws(()=>summarize(rows.slice(1)));
 const events=[{event:'queued',key:'a',home:3,time:0,active:0,queued:1},
  {event:'admitted',key:'a',home:3,device:0,time:2,active:1,queued:0},
  {event:'released',key:'a',device:0,time:3,active:0,queued:0}];
 assert.equal(queue(events,'shared').migrations,1);assert.throws(()=>queue(events,'fixed'));
}
tests();
if(process.argv[2]){
 const dir=process.argv[2],hashes={};
 const read=name=>{const raw=fs.readFileSync(`${dir}/${name}`);hashes[name]=sha(raw);return JSON.parse(raw);};
 const rows=read('runs.json'),summary=read('summary.json');
 assert.equal(rows.length,32);assert.equal(new Set(rows.map(r=>r.index)).size,32);
 assert.ok(summary.gpu_seconds>0&&summary.gpu_seconds<=36000);close(summary.gpu_hours,summary.gpu_seconds/3600);
 assert.equal(summary.complete,rows.filter(r=>r.complete).length);
 if(summary.complete!==32){assert.equal(summary.predeclared_success_gate_met,false);console.log(JSON.stringify({passed:true,incomplete:true,hashes}));}
 else{
  for(const r of rows){assert.equal(r.block,Math.floor(r.index/8));assert.equal(r.repeat,Math.floor(r.block/2));
   assert.equal(r.pool_mode,ORDER[r.block]);assert.equal(r.arm,'old_fast');assert.equal(r.run_seconds,1020);assert.equal(r.pool_seconds,1180);}
  const by=summarize(rows),cs=contrast(by);
  for(const r of by){const ref=summary.by_pool.find(v=>v.block===r.block&&v.task===r.task);for(const k of ['best','median','sample_sd'])close(r[k],ref[k]);}
  for(const r of cs){const ref=summary.contrasts.find(v=>v.repeat===r.repeat&&v.task===r.task);for(const k of ['fixed_best','shared_best','oriented_delta','median_delta'])close(r[k],ref[k]);}
  const pass=cs.every(r=>r.oriented_delta>=(r.task===TASKS[1]?.001:-1e-12));assert.equal(summary.quality_gate,pass);
  const qs=ORDER.map((mode,b)=>queue(read(`queue-${b}.json`),mode));
  qs.forEach((q,b)=>{const ref=summary.queues[b];for(const k of ['admissions','migrations','wait_total'])close(q[k],ref[k]);q.wait_median===null?assert.equal(ref.wait_median,null):close(q.wait_median,ref.wait_median);});
  const input=read('input-checks.json');assert.equal(input.length,32);assert.ok(input.every(x=>x.passed&&x.expected_sha256===x.observed_sha256));
  const ids=read('identity.json');assert.equal(ids.length,4);ids.forEach(x=>{assert.deepEqual(x.execution,ids[0].execution);assert.equal(new Set([...x.execution,...x.service]).size,6);});
  const changed=qs.filter((_,i)=>ORDER[i]==='shared').every(q=>q.migrations>0);assert.equal(summary.dispatch_changed,changed);
  assert.equal(summary.predeclared_success_gate_met,pass&&summary.structural_gate&&summary.runtime_input_gate&&summary.actual_mode_gate&&changed);
  console.log(JSON.stringify({passed:true,assigned:32,quality_gate:pass,predeclared_success_gate_met:summary.predeclared_success_gate_met,
    gpu_hours:summary.gpu_hours,contrasts:cs,queues:qs,hashes},null,2));
 }
}else console.log(JSON.stringify({selftests:'passed',model_calls:0,gpu_calls:0}));
