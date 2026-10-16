// Independent selective admission/quality audit. Does not execute the Python reader.
// Adapts the previously independent32-denominator audit; no private score access.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const TASKS=['aerial-cactus-identification','denoising-dirty-documents'];
const ORDER=['shared','selective','selective','shared'];
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
  const a=by.find(r=>r.repeat===repeat&&r.task===task&&r.pool_mode==='shared');
  const b=by.find(r=>r.repeat===repeat&&r.task===task&&r.pool_mode==='selective');
  const sign=task===TASKS[0]?1:-1;
  out.push({repeat,task,baseline_best:a.best,selective_best:b.best,oriented_delta:sign*(b.best-a.best),median_delta:sign*(b.median-a.median)});
 }
 return out;
}
function queue(events,mode){
 assert.ok(['shared','selective'].includes(mode));
 const cap=mode==='selective'?2:1, pending=[],active=Array.from({length:4},()=>new Set()),seen=new Set(),submitted=new Map(),waits=[];
 let migrations=0,co_admissions=0,peak_device_leases=0,protected_deferrals=0,last=-Infinity; const deferred=new Set();
 const protectedKey=k=>{assert.match(k,/^\d+(?::|$)/);return Number(k.split(':')[0])%2===1;};
 for(const e of events){
  assert.ok(Number.isFinite(e.time)&&e.time>=last);last=e.time;
  if(e.event==='queued'){
   assert.ok(!seen.has(e.key));seen.add(e.key);pending.push({key:e.key,home:e.home});submitted.set(e.key,e.time);
  }else if(e.event==='admitted'){
   assert.ok(pending.length>0);const r=pending[0];assert.equal(r.key,e.key);
   const choices=[0,1,2,3].filter(d=>!active[d].size||(mode==='selective'&&active[d].size<cap&&!protectedKey(e.key)&&[...active[d]].every(k=>!protectedKey(k)))).sort((a,b)=>active[a].size-active[b].size||a-b);
   assert.ok(choices.length>0);assert.equal(e.device,choices[0]);
   co_admissions+=active[e.device].size>0;
   pending.shift();active[e.device].add(e.key);peak_device_leases=Math.max(peak_device_leases,active[e.device].size);
   migrations+=e.device!==r.home;waits.push(e.time-submitted.get(e.key));
  }else if(e.event==='released'){assert.ok(active[e.device].delete(e.key));}
  else if(e.event==='queue_cancelled'){
   const at=pending.findIndex(x=>x.key===e.key);assert.ok(at>=0);pending.splice(at,1);
  }else throw Error('unknown queue event');
  assert.equal(e.active,active.reduce((n,x)=>n+x.size,0));assert.equal(e.queued,pending.length);
  if(mode==='selective'&&pending.length&&protectedKey(pending[0].key)&&active.every(x=>x.size>0)&&active.some(x=>x.size<2)&&!deferred.has(pending[0].key)){
   deferred.add(pending[0].key);protected_deferrals++;
  }
 }
 assert.equal(pending.length,0);assert.ok(active.every(x=>x.size===0));waits.sort((a,b)=>a-b);
 return {admissions:waits.length,migrations,co_admissions,peak_device_leases,protected_deferrals,wait_total:waits.reduce((a,b)=>a+b,0),
  wait_median:waits.length?(waits[Math.floor(waits.length/2)]+waits[Math.floor((waits.length-1)/2)])/2:null};
}
function tests(){
 const rows=Array.from({length:32},(_,i)=>({block:Math.floor(i/8),task:TASKS[i%2],score:i%2?.02-(ORDER[Math.floor(i/8)]==='selective'?.002:0):.99}));
 const q=contrast(summarize(rows));assert.ok(q.every(r=>r.oriented_delta>=(r.task===TASKS[1]?.001:-1e-12)));
 rows[16].score=.90;rows[18].score=.90;rows[20].score=.90;rows[22].score=.90;
 assert.ok(contrast(summarize(rows)).some(r=>r.oriented_delta<0));assert.throws(()=>summarize(rows.slice(1)));
 const events=[{event:'queued',key:'0:a',home:3,time:0,active:0,queued:1},
  {event:'admitted',key:'0:a',home:3,device:0,time:2,active:1,queued:0},
  {event:'released',key:'0:a',device:0,time:3,active:0,queued:0}];
 assert.equal(queue(events,'shared').migrations,1);assert.throws(()=>queue(events,'fixed'));
 const es=[];for(let i=0;i<8;i++)es.push({event:'queued',key:String(2*i),home:i%4,time:i,active:0,queued:i+1});
 for(let i=0;i<8;i++)es.push({event:'admitted',key:String(2*i),device:i%4,time:10+i,active:i+1,queued:7-i});
 for(let i=0;i<8;i++)es.push({event:'released',key:String(2*i),device:i%4,time:20+i,active:7-i,queued:0});
 assert.equal(queue(es,'selective').co_admissions,4);assert.equal(queue(es,'selective').peak_device_leases,2);
 assert.throws(()=>queue(es,'shared'));
 const bad=structuredClone(es);bad[8].key='1';assert.throws(()=>queue(bad,'selective'));
 const wrong=structuredClone(es);wrong[9].device=0;assert.throws(()=>queue(wrong,'selective'));
 const protectedEvents=es.slice(0,0);
 for(let i=0;i<4;i++){
  protectedEvents.push({event:'queued',key:String(2*i),home:i,time:2*i,active:i,queued:1});
  protectedEvents.push({event:'admitted',key:String(2*i),device:i,time:2*i+1,active:i+1,queued:0});
 }
 protectedEvents.push({event:'queued',key:'1:p',home:0,time:8,active:4,queued:1},
  {event:'released',key:'0',device:0,time:9,active:3,queued:1},
  {event:'admitted',key:'1:p',device:0,time:10,active:4,queued:0},
  {event:'released',key:'1:p',device:0,time:11,active:3,queued:0});
 for(let i=1;i<4;i++)protectedEvents.push({event:'released',key:String(2*i),device:i,time:11+i,active:3-i,queued:0});
 const protectedAudit=queue(protectedEvents,'selective');assert.equal(protectedAudit.protected_deferrals,1);assert.equal(protectedAudit.co_admissions,0);
 const forbidden=structuredClone(es);for(const e of forbidden)if(e.key==='8')e.key='1:p';
 assert.throws(()=>queue(forbidden,'selective'));
}
tests();
if(process.argv[2]){
 const dir=process.argv[2],pin=process.argv[3],hashes={};assert.match(pin||'',/^[a-f0-9]{64}$/);
 const read=name=>{const raw=fs.readFileSync(`${dir}/${name}`);hashes[name]=sha(raw);return JSON.parse(raw);};
 const rows=read('runs.json'),summary=read('summary.json');assert.equal(summary.plan_sha256,pin);assert.equal(summary.assigned,32);
 assert.equal(rows.length,32);assert.equal(new Set(rows.map(r=>r.index)).size,32);
 assert.ok(summary.gpu_seconds>0&&summary.gpu_seconds<=36000);close(summary.gpu_hours,summary.gpu_seconds/3600);
 assert.equal(summary.complete,rows.filter(r=>r.complete).length);
 if(summary.complete!==32){assert.equal(summary.predeclared_success_gate_met,false);console.log(JSON.stringify({passed:true,incomplete:true,hashes}));}
 else{
  for(const r of rows){assert.equal(r.block,Math.floor(r.index/8));assert.equal(r.repeat,Math.floor(r.block/2));
   assert.equal(r.pool_mode,ORDER[r.block]);assert.equal(r.task,TASKS[r.index%2]);assert.equal(r.seed,217701+100*r.repeat+r.index%8);assert.equal(r.arm,'old_fast');assert.equal(r.run_seconds,1020);assert.equal(r.pool_seconds,1180);}
  const by=summarize(rows),cs=contrast(by);
  for(const r of by){const ref=summary.by_pool.find(v=>v.block===r.block&&v.task===r.task);for(const k of ['best','median','sample_sd'])close(r[k],ref[k]);}
  for(const r of cs){const ref=summary.contrasts.find(v=>v.repeat===r.repeat&&v.task===r.task);for(const k of ['baseline_best','selective_best','oriented_delta','median_delta'])close(r[k],ref[k]);}
  const pass=cs.every(r=>r.oriented_delta>=(r.task===TASKS[1]?.001:-1e-12));assert.equal(summary.quality_gate,pass);
  const qs=ORDER.map((mode,b)=>queue(read(`queue-${b}.json`),mode));
  qs.forEach((q,b)=>{const ref=summary.queues[b];for(const k of ['admissions','migrations','co_admissions','peak_device_leases','protected_deferrals','wait_total'])close(q[k],ref[k]);q.wait_median===null?assert.equal(ref.wait_median,null):close(q.wait_median,ref.wait_median);});
  const input=read('input-checks.json');assert.equal(input.length,32);assert.ok(input.every(x=>x.passed&&x.expected_sha256===x.observed_sha256));
  const ids=read('identity.json');assert.equal(ids.length,4);ids.forEach(x=>{assert.deepEqual(x.execution,ids[0].execution);assert.equal(new Set([...x.execution,...x.service]).size,6);});
  const coexist=read('coexistence.json');assert.ok(coexist.passed&&coexist.cleanup_verified);assert.equal(coexist.containers,2);
  assert.deepEqual(coexist.rows.map(r=>r.slot).sort(),[0,1]);coexist.rows.forEach(r=>{assert.ok(r.passed&&r.both_ready&&r.both_done);assert.equal(r.devices,1);assert.equal(r.result,16777216);assert.equal(r.held_bytes,134217728);});
  const changed=qs.filter((_,i)=>ORDER[i]==='selective').every(q=>q.co_admissions>0&&q.protected_deferrals>0);assert.equal(summary.dispatch_changed,changed);
  assert.equal(summary.predeclared_success_gate_met,pass&&summary.structural_gate&&summary.runtime_input_gate&&summary.actual_mode_gate&&changed);
  console.log(JSON.stringify({passed:true,assigned:32,quality_gate:pass,predeclared_success_gate_met:summary.predeclared_success_gate_met,
    summary_sha256:hashes['summary.json'],plan_sha256:pin,gpu_hours:summary.gpu_hours,contrasts:cs,queues:qs,hashes},null,2));
 }
}else console.log(JSON.stringify({selftests:'passed',model_calls:0,gpu_calls:0}));


