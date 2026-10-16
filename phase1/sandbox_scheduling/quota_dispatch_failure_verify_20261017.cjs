// Independent replay of sealed19004 metadata. Never repairs/relaxes its gate.
const fs=require('fs'),crypto=require('crypto'),assert=require('assert/strict');
const dir=process.argv[2];assert.ok(dir);const hashes={};
const read=n=>{const raw=fs.readFileSync(`${dir}/${n}`);hashes[n]=crypto.createHash('sha256').update(raw).digest('hex');return JSON.parse(raw);};
const manifest=read('remote-manifest.json');
for(const [name,pin] of Object.entries(manifest.files)){
 const raw=fs.readFileSync(`${dir}/${name}`);assert.equal(raw.length,pin.bytes);
 assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),pin.sha256);
}
const closure=read('closure.json'),binding=read('hook-bindings.json'),runs=read('runs.json');
assert.equal(closure.assigned,32);assert.equal(runs.length,32);assert.ok(runs.every(r=>r.started&&r.complete));
assert.equal(binding.runtime_is_advertised,false);assert.equal(binding.runtime_is_deep_dispatch,true);
assert.equal(binding.worker_resolves_runtime_binding,true);
const rows=[],order=['partitioned','pooled','pooled','partitioned'];
const rank=(a,b)=>(Number(b.role==='analyze')-Number(a.role==='analyze'))||a.requested-b.requested||a.run-b.run;
for(let b=0;b<4;b++){
 const ev=read(`generation-${b}.json`),waiting=new Map(),active=new Map(),seen=new Set();
 let last=-Infinity,admissions=0,borrowed=0,peak=0,globalViolations=0,oldViolations=0;
 const examples=[];
 for(let n=0;n<ev.length;n++){
  const e=ev[n];assert.ok(Number.isFinite(e.time)&&e.time>=last);last=e.time;
  if(e.event==='queued'){
   const r=e.request;assert.equal(Math.floor(r.run/8),b);assert.ok(!seen.has(r.key));seen.add(r.key);waiting.set(r.key,r);
  }else if(e.event==='admitted'){
   const r=waiting.get(e.key);assert.ok(r);assert.ok(active.size<4);
   const same=[...active.values()].filter(x=>x.task===r.task).length;
   const eligible=[...waiting.values()].filter(x=>order[b]==='pooled'||[...active.values()].filter(y=>x.task===y.task).length<2).sort(rank);
   const old=[...waiting.values()].filter(x=>x.task===r.task).sort(rank);
   const mismatch=eligible[0]?.key!==e.key;globalViolations+=Number(mismatch);
   oldViolations+=Number(same>=2||old[0]?.key!==e.key);borrowed+=Number(same>=2);admissions++;
   if(mismatch&&examples.length<3)examples.push({event_index:n,actual_key:e.key,expected_key:eligible[0]?.key??null,
    actual_role:r.role,expected_role:eligible[0]?.role??null,active:active.size});
   waiting.delete(e.key);active.set(e.key,r);peak=Math.max(peak,active.size);
  }else if(e.event==='released')assert.ok(active.delete(e.key));
  else if(e.event==='cancelled')assert.ok(waiting.delete(e.key));
  else throw Error('unexpected event');
 }
 assert.equal(waiting.size,0);assert.equal(active.size,0);
 rows.push({block:b,declared_mode:order[b],requests:seen.size,admissions,borrowed_admissions:borrowed,
  peak_active:peak,declared_global_order_violations:globalViolations,legacy_per_task_order_violations:oldViolations,examples});
}
assert.ok(rows.some(r=>r.declared_global_order_violations>0));
console.log(JSON.stringify({passed:true,assigned:32,complete:32,transport_hashes_verified:Object.keys(manifest.files).length,
 planned_intervention_verified:false,original_success_gate_met:false,quality_comparison_valid:false,
 actual_legacy_per_task_order_all_pools:rows.every(r=>r.legacy_per_task_order_violations===0),
 actual_borrowing:rows.reduce((s,r)=>s+r.borrowed_admissions,0),rows,hashes,
 limits:['Post-failure structure verification, not a replacement frozen quality readout.','The hook binding is an independent frozen-entry CPU observation, not historical instrumentation.','Original failed readout and all32 assignments/cost remain preserved.']},null,2));
