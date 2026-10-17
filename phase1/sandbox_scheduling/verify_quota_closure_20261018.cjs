// Independent metadata/statistics audit; no imputation or replacement readout.
const fs=require('fs'),vm=require('vm'),crypto=require('crypto'),assert=require('assert/strict');
const dir=process.argv[2];assert.ok(dir);
const read=n=>JSON.parse(fs.readFileSync(`${dir}/${n}`));
const manifest=read('remote-manifest.json');
for(const [n,h] of Object.entries(manifest.files)){
 const raw=fs.readFileSync(`${dir}/${n}`);
 assert.equal(raw.length,h.bytes);assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),h.sha256);
}
const c=read('closure.json'),s=read('summary.json'),r=read('runs.json'),workers=read('worker-closure.json');
assert.equal(c.job,'19136');assert.equal(s.plan_sha256,'2736fb9326f62f3c83bc0cebc4854ba629991e5b5e4bb69e708aa91e24b74e7e');
assert.equal(r.length,32);assert.equal(new Set(r.map(x=>x.index)).size,32);
assert.equal(c.gpu_seconds,c.elapsed_seconds*6);assert.equal(s.gpu_seconds,c.gpu_seconds);assert.ok(c.gpu_seconds<=36000);
assert.equal(s.complete,r.filter(x=>x.complete).length);assert.equal(s.complete,31);
const order=['partitioned','pooled','pooled','partitioned'],tasks=['aerial-cactus-identification','denoising-dirty-documents'];
for(const x of r){
 assert.equal(x.block,Math.floor(x.index/8));assert.equal(x.quota_mode,order[x.block]);assert.equal(x.task,tasks[x.index%2]);
 assert.equal(x.seed,217901+100*Math.floor(x.block/2)+x.index%8);assert.equal(x.run_seconds,1020);assert.equal(x.pool_seconds,1180);
 const w=workers.find(y=>y.index===x.index);assert.equal(x.complete,w.complete);assert.equal(x.cleanup,true);
 if(!x.complete)assert.equal(x.score,null);
}
assert.equal(s.predeclared_success_gate_met,false);assert.equal(s.incomplete,true);
assert.ok(c.service_cleanup.gpu_clean);assert.ok(c.blocks.every(x=>x.execution_closed.gpu_clean&&!x.execution_closed.telemetry_errors.length));
// Reuse the independent, previously frozen Node replay without its CLI or tests.
const src=fs.readFileSync(`${__dirname}/verify_generation_quota_20261017.cjs`,'utf8');
assert.equal(src.split('selftest();').length,2);
const replay=vm.runInNewContext(src.split('selftest();')[0]+'\n;({gen,execution});',{require,console});
const generations=[],executions=[];
for(let b=0;b<4;b++){
 generations.push({block:b,...replay.gen(read(`generation-${b}.json`),order[b])});
 executions.push({block:b,...replay.execution(read(`queue-${b}.json`))});
}
assert.ok(generations.filter((_,b)=>order[b]==='pooled').every(x=>x.borrowed_admissions>0));
assert.ok(generations.filter((_,b)=>order[b]==='partitioned').every(x=>x.borrowed_admissions===0));
// All8 task/pools kept. No best is assigned to an incomplete pool.
const groups=[];
for(let b=0;b<4;b++)for(const task of tasks){
 const a=r.filter(x=>x.block===b&&x.task===task);assert.equal(a.length,4);
 const values=a.filter(x=>x.complete).map(x=>x.score).sort((a,b)=>a-b);
 assert.ok(values.every(Number.isFinite));
 const mean=values.reduce((a,b)=>a+b,0)/values.length;
 groups.push({block:b,task,assigned:4,complete:values.length,
  best:values.length===4?(task===tasks[0]?values[3]:values[0]):null,
  median:values.length===4?(values[1]+values[2])/2:null,
  sample_sd:values.length===4?Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/3):null});
}
const contrasts=[];
for(let rep=0;rep<2;rep++)for(const task of tasks){
 const b=groups.find(x=>Math.floor(x.block/2)===rep&&x.task===task&&order[x.block]==='partitioned');
 const p=groups.find(x=>Math.floor(x.block/2)===rep&&x.task===task&&order[x.block]==='pooled');
 const complete=b.complete===4&&p.complete===4;
 contrasts.push({repeat:rep,task,complete_pair:complete,
  partitioned_best:b.best,pooled_best:p.best,
  oriented_delta:complete?(task===tasks[0]?1:-1)*(p.best-b.best):null});
}
const result={passed:true,assigned:32,complete:31,failed_indices:workers.filter(x=>!x.complete).map(x=>x.index),
 transport_hashes_verified:Object.keys(manifest.files).length,gpu_seconds:c.gpu_seconds,gpu_hours:c.gpu_seconds/3600,
 intervention_verified:true,generations,executions,quality_comparison_valid:false,original_success_gate_met:false,
 descriptive_only_complete_task_pools:groups,descriptive_only_contrasts:contrasts,
 any_complete_denoise_contrast_fails_original_threshold:contrasts.some(x=>x.task===tasks[1]&&x.complete_pair&&x.oriented_delta<.001),
 limitation:'Frozen global32 gate remains failed/incomplete. Complete task-pair diagnostics do not convert this into a valid controlled comparison; no missing-row or empty-pool imputation.'};
if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2),{flag:'wx'});
console.log(JSON.stringify(result,null,2));
