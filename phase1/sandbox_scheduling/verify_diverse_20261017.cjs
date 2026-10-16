// Independent Node arithmetic/dispatch audit, not an independent pristine scorer.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const TASKS=['aerial-cactus-identification','denoising-dirty-documents'];
const ORDER=['shared','colocated','diverse','diverse','colocated','shared'];
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const close=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-12);
function task(key){assert.match(key,/^\d+(?::|$)/);return Number(key.split(':')[0])%2;}
function summary(rows){
 const blocks=[];
 for(let block=0;block<6;block++)for(const t of TASKS){
  const v=rows.filter(r=>r.block===block&&r.task===t).map(r=>r.score).sort((a,b)=>a-b);
  assert.equal(v.length,4);assert.ok(v.every(Number.isFinite));const mean=v.reduce((a,b)=>a+b)/4;
  blocks.push({block,repeat:Math.floor(block/3),pool_mode:ORDER[block],task:t,
   best:t===TASKS[0]?v[3]:v[0],median:(v[1]+v[2])/2,
   sample_sd:Math.sqrt(v.reduce((a,x)=>a+(x-mean)**2,0)/3),n:4});
 }
 const contrasts=[];
 for(let repeat=0;repeat<2;repeat++)for(const t of TASKS)for(const control of ['shared','colocated']){
  const a=blocks.find(r=>r.repeat===repeat&&r.task===t&&r.pool_mode===control);
  const b=blocks.find(r=>r.repeat===repeat&&r.task===t&&r.pool_mode==='diverse');
  const sign=t===TASKS[0]?1:-1;
  contrasts.push({repeat,task:t,control,baseline_best:a.best,diverse_best:b.best,
   oriented_delta:sign*(b.best-a.best),median_delta:sign*(b.median-a.median)});
 }
 return {blocks,contrasts,gate:contrasts.every(r=>r.oriented_delta>=(r.task===TASKS[1]?.001:-1e-12))};
}
function queue(events,mode){
 assert.ok(ORDER.includes(mode));const cap=mode==='shared'?1:2;
 const pending=[],active=Array.from({length:4},()=>new Set()),seen=new Set(),arrivals=new Map(),waits=[];
 let co_admissions=0,changed_device_choices=0,same_task_co_admissions=0,peak_device_leases=0,migrations=0,last=-Infinity;
 for(const e of events){
  task(e.key);assert.ok(Number.isFinite(e.time)&&e.time>=last);last=e.time;
  if(e.event==='queued'){
   assert.ok(!seen.has(e.key));seen.add(e.key);pending.push(e);arrivals.set(e.key,e.time);
  }else if(e.event==='admitted'){
   assert.equal(pending[0]?.key,e.key);const p=pending[0];
   const choices=[0,1,2,3].filter(d=>active[d].size<cap);assert.ok(choices.length);
   const same=d=>[...active[d]].filter(k=>task(k)===task(e.key)).length;
   const baseline=[...choices].sort((a,b)=>active[a].size-active[b].size||a-b)[0];
   choices.sort((a,b)=>active[a].size-active[b].size||(mode==='diverse'?same(a)-same(b):0)||a-b);
   assert.equal(e.device,choices[0]);co_admissions+=active[e.device].size>0;
   same_task_co_admissions+=same(e.device)>0;changed_device_choices+=e.device!==baseline;
   migrations+=e.device!==p.home;waits.push(e.time-arrivals.get(e.key));pending.shift();active[e.device].add(e.key);
   peak_device_leases=Math.max(peak_device_leases,active[e.device].size);
  }else if(e.event==='released'){assert.ok(active[e.device]?.delete(e.key));}
  else if(e.event==='queue_cancelled'){
   const at=pending.findIndex(x=>x.key===e.key);assert.ok(at>=0);pending.splice(at,1);
  }else throw Error('unknown event');
  assert.equal(e.active,active.reduce((n,s)=>n+s.size,0));assert.equal(e.queued,pending.length);
 }
 assert.equal(pending.length,0);assert.ok(active.every(s=>!s.size));waits.sort((a,b)=>a-b);
 return {admissions:waits.length,migrations,co_admissions,changed_device_choices,same_task_co_admissions,
  peak_device_leases,wait_total:waits.reduce((a,b)=>a+b,0),
  wait_median:waits.length?(waits[Math.floor(waits.length/2)]+waits[Math.floor((waits.length-1)/2)])/2:null};
}
function tests(){
 const rows=Array.from({length:48},(_,i)=>({block:Math.floor(i/8),task:TASKS[i%2],
  score:i%2?.02-(ORDER[Math.floor(i/8)]==='diverse'?.002:0):.99}));
 assert.equal(summary(rows).gate,true);assert.equal(summary(rows).contrasts.length,8);
 const stronger=structuredClone(rows);stronger.filter(r=>r.block===1&&r.task===TASKS[1]).forEach(r=>r.score=.017);
 assert.equal(summary(stronger).gate,false);assert.throws(()=>summary(rows.slice(1)));
 const incomplete=structuredClone(rows);incomplete[0].score=null;assert.throws(()=>summary(incomplete));
 const es=[],keys=['0:a','1:a','2:a','3:a','4:a'];
 keys.forEach((key,i)=>es.push({event:'queued',key,home:i%4,time:i,active:0,queued:i+1}));
 const devices=[0,1,2,3,1];
 keys.forEach((key,i)=>es.push({event:'admitted',key,device:devices[i],time:10+i,active:i+1,queued:4-i}));
 keys.forEach((key,i)=>es.push({event:'released',key,device:devices[i],time:20+i,active:4-i,queued:0}));
 assert.equal(queue(es,'diverse').changed_device_choices,1);assert.equal(queue(es,'diverse').same_task_co_admissions,0);
 assert.throws(()=>queue(es,'colocated'));assert.throws(()=>queue(es,'shared'));
 const wrong=structuredClone(es);wrong[5].key='1:a';assert.throws(()=>queue(wrong,'diverse'));
 assert.throws(()=>task('not-a-number'));
}
tests();
if(process.argv[2]){
 const dir=process.argv[2],pin=process.argv[3],hashes={};assert.match(pin||'',/^[a-f0-9]{64}$/);
 function read(n){const raw=fs.readFileSync(`${dir}/${n}`);hashes[n]=digest(raw);return JSON.parse(raw);}
 const rows=read('runs.json'),s=read('summary.json');assert.equal(s.plan_sha256,pin);
 assert.equal(rows.length,48);assert.equal(new Set(rows.map(r=>r.index)).size,48);assert.equal(s.assigned,48);
 assert.equal(s.complete,rows.filter(r=>r.complete).length);assert.equal(s.started,rows.filter(r=>r.started).length);
 assert.ok(s.gpu_seconds>0&&s.gpu_seconds<=50400);close(s.gpu_hours,s.gpu_seconds/3600);
 const groups=new Map();
 for(const r of rows){
  assert.ok(Number.isInteger(r.index)&&r.index>=0&&r.index<48);assert.equal(r.block,Math.floor(r.index/8));
  assert.equal(r.task,TASKS[r.index%2]);assert.equal(r.repeat,Math.floor(r.block/3));assert.equal(r.pool_mode,ORDER[r.block]);
  assert.equal(r.seed,217501+100*r.repeat+r.index%8);assert.equal(r.arm,'old_fast');
  assert.equal(r.run_seconds,1020);assert.equal(r.pool_seconds,1180);
  const group=groups.get(r.seed)||[];group.push(r);groups.set(r.seed,group);
 }
 assert.equal(groups.size,16);for(const g of groups.values())assert.deepEqual(g.map(r=>r.pool_mode).sort(),['colocated','diverse','shared']);
 if(s.complete!==48){assert.equal(s.predeclared_success_gate_met,false);console.log(JSON.stringify({passed:true,incomplete:true,summary_sha256:hashes['summary.json'],plan_sha256:pin,hashes}));}
 else{
  const q=summary(rows);assert.equal(s.by_pool.length,12);assert.equal(s.contrasts.length,8);
  q.blocks.forEach(r=>{const ref=s.by_pool.find(x=>x.block===r.block&&x.task===r.task);for(const k of ['best','median','sample_sd'])close(r[k],ref[k]);});
  q.contrasts.forEach(r=>{const ref=s.contrasts.find(x=>x.repeat===r.repeat&&x.task===r.task&&x.control===r.control);for(const k of ['baseline_best','diverse_best','oriented_delta','median_delta'])close(r[k],ref[k]);});
  assert.equal(s.quality_gate,q.gate);
  const queues=ORDER.map((mode,i)=>queue(read(`queue-${i}.json`),mode));
  queues.forEach((r,i)=>{for(const k of Object.keys(r))r[k]===null?assert.equal(s.queues[i][k],null):close(s.queues[i][k],r[k]);});
  const inputs=read('input-checks.json');assert.equal(inputs.length,48);assert.ok(inputs.every(x=>x.passed&&x.expected_sha256===x.observed_sha256));
  const ids=read('identity.json');assert.equal(ids.length,6);ids.forEach(x=>{assert.deepEqual(x.execution,ids[0].execution);assert.equal(new Set([...x.execution,...x.service]).size,6);assert.deepEqual([...x.service].sort(),[...ids[0].service].sort());});
  const coexist=read('coexistence.json');assert.ok(coexist.passed&&coexist.cleanup_verified);assert.equal(coexist.containers,2);
  coexist.rows.forEach(r=>{assert.ok(r.passed&&r.both_ready&&r.both_done);assert.equal(r.devices,1);assert.equal(r.result,16777216);});
  const changed=queues.every((r,i)=>ORDER[i]==='shared'||r.co_admissions>0)&&queues.every((r,i)=>ORDER[i]!=='diverse'||r.changed_device_choices>0);
  assert.equal(s.dispatch_changed,changed);
  assert.equal(s.predeclared_success_gate_met,Boolean(q.gate&&s.structural_gate&&s.runtime_input_gate&&s.actual_mode_gate&&changed));
  console.log(JSON.stringify({passed:true,assigned:48,quality_gate:q.gate,predeclared_success_gate_met:s.predeclared_success_gate_met,
   summary_sha256:hashes['summary.json'],plan_sha256:pin,gpu_hours:s.gpu_hours,contrasts:q.contrasts,queues,hashes},null,2));
 }
}else console.log(JSON.stringify({selftests:'passed',model_calls:0,gpu_calls:0}));
