// Independent full-denominator statistics and numerical request/lease replay.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const tasks=['aerial-cactus-identification','denoising-dirty-documents'];
const order=['partitioned','pooled','pooled','partitioned'];
const near=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-10);
function gen(events,mode){
 assert.ok(order.includes(mode));const waiting=new Map(),active=new Map(),seen=new Set();let borrowed=0,peak=0,last=-Infinity;
 for(const e of events){
  assert.ok(Number.isFinite(e.time)&&e.time>=last);last=e.time;
  if(e.event==='queued'){const r=e.request;assert.ok(!seen.has(r.key));seen.add(r.key);waiting.set(r.key,r);}
  else if(e.event==='admitted'){
   assert.ok(active.size<4);const eligible=[...waiting.values()].filter(r=>mode==='pooled'||[...active.values()].filter(x=>x.task===r.task).length<2);
   eligible.sort((a,b)=>(Number(b.role==='analyze')-Number(a.role==='analyze'))||a.requested-b.requested||a.run-b.run);
   assert.ok(eligible.length);const chosen=eligible[0];assert.equal(e.key,chosen.key);
   borrowed+=Number([...active.values()].filter(r=>r.task===chosen.task).length>=2);
   waiting.delete(e.key);active.set(e.key,chosen);peak=Math.max(peak,active.size);
  }else if(e.event==='released')assert.ok(active.delete(e.key));
  else if(e.event==='cancelled')assert.ok(waiting.delete(e.key));
  else throw Error('unknown generation event');
 }
 assert.equal(active.size,0);assert.equal(waiting.size,0);return {requests:seen.size,borrowed_admissions:borrowed,peak_active:peak};
}
function execution(events){
 let active=new Map(),pending=[],seen=new Set(),last=-Infinity,admissions=0,migrations=0;const waits=[],requested=new Map();
 for(const e of events){
  assert.ok(Number.isFinite(e.time)&&e.time>=last);last=e.time;
  if(e.event==='queued'){assert.ok(!seen.has(e.key));seen.add(e.key);pending.push(e.key);requested.set(e.key,e);}
  else if(e.event==='admitted'){
   assert.equal(pending.shift(),e.key);const available=[0,1,2,3].filter(d=>![...active.values()].includes(d));
   assert.ok(available.length);assert.equal(e.device,available[0]);active.set(e.key,e.device);
   admissions++;migrations+=Number(e.device!==requested.get(e.key).home);waits.push(e.time-requested.get(e.key).time);
  }else if(e.event==='released'){assert.equal(active.get(e.key),e.device);assert.ok(active.delete(e.key));}
  else if(e.event==='queue_cancelled'){const at=pending.indexOf(e.key);assert.ok(at>=0);pending.splice(at,1);}
  else throw Error('unknown execution event');
  assert.equal(active.size,e.active);assert.equal(pending.length,e.queued);
 }
 assert.equal(active.size,0);assert.equal(pending.length,0);return {admissions,migrations,wait_total:waits.reduce((a,b)=>a+b,0)};
}
function statistics(rows){
 const by=[];for(let b=0;b<4;b++)for(const task of tasks){
  const v=rows.filter(r=>r.block===b&&r.task===task).map(r=>r.score).sort((a,b)=>a-b);assert.equal(v.length,4);assert.ok(v.every(Number.isFinite));
  const mean=v.reduce((a,b)=>a+b,0)/4;by.push({block:b,task,best:task===tasks[0]?v[3]:v[0],median:(v[1]+v[2])/2,sample_sd:Math.sqrt(v.reduce((a,b)=>a+(b-mean)**2,0)/3)});
 }
 const contrasts=[];for(let rep=0;rep<2;rep++)for(const task of tasks){
  const base=by.find(r=>Math.floor(r.block/2)===rep&&r.task===task&&order[r.block]==='partitioned');
  const method=by.find(r=>Math.floor(r.block/2)===rep&&r.task===task&&order[r.block]==='pooled');const s=task===tasks[0]?1:-1;
  contrasts.push({repeat:rep,task,partitioned_best:base.best,pooled_best:method.best,oriented_delta:s*(method.best-base.best),median_delta:s*(method.median-base.median)});
 }
 return {by,contrasts,quality:contrasts.every(x=>x.oriented_delta>=(x.task===tasks[1]?.001:-1e-12))};
}
function selftest(){
 const e=[];for(let i=0;i<4;i++)e.push({event:'queued',time:i*2,request:{key:String(i),task:'a',role:'improve',requested:i,run:i}},{event:'admitted',time:i*2+1,key:String(i)});
 for(let i=0;i<4;i++)e.push({event:'released',time:10+i,key:String(i)});
 assert.equal(gen(e,'pooled').borrowed_admissions,2);assert.throws(()=>gen(e,'partitioned'));
 const rows=Array.from({length:32},(_,i)=>({block:Math.floor(i/8),task:tasks[i%2],score:i%2?.02-(order[Math.floor(i/8)]==='pooled'?.002:0):.99}));
 assert.ok(statistics(rows).quality);rows[8].score=.999;rows[9].score=.03;assert.throws(()=>statistics(rows.slice(1)));
 assert.throws(()=>execution([{event:'queued',key:'a',home:0,time:0,active:0,queued:1},{event:'admitted',key:'a',device:1,time:1,active:1,queued:0}]));
}
selftest();
if(process.argv[2]){
 const dir=process.argv[2],pin=process.argv[3],hashes={};assert.match(pin||'',/^[a-f0-9]{64}$/);
 const read=n=>{const raw=fs.readFileSync(`${dir}/${n}`);hashes[n]=crypto.createHash('sha256').update(raw).digest('hex');return JSON.parse(raw);};
 const rows=read('runs.json'),s=read('summary.json');assert.equal(s.plan_sha256,pin);assert.equal(s.assigned,32);assert.equal(rows.length,32);
 assert.equal(new Set(rows.map(r=>r.index)).size,32);assert.ok(s.gpu_seconds>0&&s.gpu_seconds<=36000);near(s.gpu_hours,s.gpu_seconds/3600);
 assert.equal(s.complete,rows.filter(r=>r.complete).length);
 if(s.complete!==32){assert.equal(s.predeclared_success_gate_met,false);console.log(JSON.stringify({passed:true,incomplete:true,hashes}));}
 else{
  for(const r of rows){assert.equal(r.block,Math.floor(r.index/8));assert.equal(r.quota_mode,order[r.block]);assert.equal(r.pool_mode,'shared');assert.equal(r.repeat,Math.floor(r.block/2));assert.equal(r.task,tasks[r.index%2]);assert.equal(r.seed,217901+100*r.repeat+r.index%8);assert.equal(r.run_seconds,1020);assert.equal(r.pool_seconds,1180);assert.equal(r.arm,'old_fast');}
  const calc=statistics(rows);assert.equal(s.quality_gate,calc.quality);
  for(const r of calc.by){const x=s.by_pool.find(x=>x.block===r.block&&x.task===r.task);['best','median','sample_sd'].forEach(k=>near(r[k],x[k]));}
  for(const r of calc.contrasts){const x=s.contrasts.find(x=>x.repeat===r.repeat&&x.task===r.task);['partitioned_best','pooled_best','oriented_delta','median_delta'].forEach(k=>near(r[k],x[k]));}
  const generations=[];for(let b=0;b<4;b++){
   const g=gen(read(`generation-${b}.json`),order[b]);generations.push(g);Object.keys(g).forEach(k=>near(g[k],s.generation_quotas[b][k]));
   const q=execution(read(`queue-${b}.json`));Object.keys(q).forEach(k=>near(q[k],s.queues[b][k]));assert.equal(s.queues[b].co_admissions,0);
  }
  const inputs=read('input-checks.json');assert.equal(inputs.length,32);assert.ok(inputs.every(x=>x.passed&&x.expected_sha256===x.observed_sha256));
  const ids=read('identity.json');assert.equal(ids.length,4);ids.forEach(x=>{assert.deepEqual(x.execution,ids[0].execution);assert.equal(new Set([...x.execution,...x.service]).size,6);});
  const co=read('coexistence.json');assert.ok(co.passed&&co.cleanup_verified);assert.equal(co.containers,2);
  const changed=generations.filter((_,b)=>order[b]==='pooled').every(x=>x.borrowed_admissions>0);assert.equal(changed,s.dispatch_changed);
  assert.equal(s.predeclared_success_gate_met,calc.quality&&changed&&s.structural_gate&&s.runtime_input_gate&&s.actual_mode_gate);
  console.log(JSON.stringify({passed:true,assigned:32,quality_gate:calc.quality,predeclared_success_gate_met:s.predeclared_success_gate_met,contrasts:calc.contrasts,generations,hashes},null,2));
 }
}else console.log(JSON.stringify({selftests:'passed',model_calls:0,gpu_calls:0}));
