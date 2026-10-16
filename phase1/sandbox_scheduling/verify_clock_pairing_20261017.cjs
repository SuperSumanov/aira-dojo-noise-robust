// Independent arithmetic/denominator check, not an independent pristine scorer.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const same=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-12);
function quality(rows){
 const blocks=[];
 for(let b=0;b<4;b++)for(let t=0;t<2;t++){
  const rs=rows.filter(r=>r.block===b&&Math.floor(r.program/2)===t);
  const valid=rs.length===2&&rs.every(r=>r.complete&&r.valid&&Number.isFinite(r.score));
  const vals=valid?rs.map(r=>r.score).sort((a,b)=>a-b):[];
  blocks.push({block:b,task_index:t,complete:valid,best:valid?(t===0?vals[1]:vals[0]):null,
   median:valid?(vals[0]+vals[1])/2:null,sample_sd:valid?Math.abs(vals[1]-vals[0])/Math.sqrt(2):null});
 }
 const contrasts=[];
 [[0,1],[3,2]].forEach(([a,b],rep)=>{for(let t=0;t<2;t++){
  const x=blocks.find(r=>r.block===a&&r.task_index===t),y=blocks.find(r=>r.block===b&&r.task_index===t);
  const complete=x.complete&&y.complete,sign=t===0?1:-1;
  contrasts.push({repeat:rep,task_index:t,complete,
   oriented_best_delta:complete?sign*(y.best-x.best):null,
   oriented_median_delta:complete?sign*(y.median-x.median):null});
 }});
 return {blocks,contrasts,gate:contrasts.every(r=>r.complete&&r.oriented_best_delta>=(r.task_index===1?.001:-1e-12))};
}
const fixture=Array.from({length:16},(_,i)=>({block:Math.floor(i/4),program:i%4,complete:true,valid:true,
 score:i%4<2?.8:.02-([1,2].includes(Math.floor(i/4))?.002:0)}));
assert.equal(quality(fixture).gate,true);fixture[0].valid=false;assert.equal(quality(fixture).gate,false);
if(process.argv[2]){
 const dir=process.argv[2],hashes={};
 function read(n){const raw=fs.readFileSync(`${dir}/${n}`);hashes[n]=digest(raw);return JSON.parse(raw);}
 const rows=read('runs.json'),s=read('summary.json');
 assert.equal(rows.length,16);assert.equal(new Set(rows.map(r=>r.index)).size,16);
 assert.equal(s.planned,16);assert.equal(s.complete,rows.filter(r=>r.complete).length);
 assert.equal(s.valid,rows.filter(r=>r.valid).length);assert.equal(s.recomputed,rows.filter(r=>r.score!==null).length);
 assert.equal(s.plan_sha256,'a2f2ea693c0d2a194ac194a3023e81645eeb55b94263733dd12e943515d6ed22');
 assert.ok(s.gpu_seconds>0&&s.gpu_seconds<=3120);same(s.gpu_hours,s.gpu_seconds/3600);
 assert.equal(s.reserved_seconds_per_condition,1460);
 const modes=['within','cross','cross','within'];
 rows.forEach(r=>{assert.equal(r.block,Math.floor(r.index/4));assert.equal(r.program,r.index%4);assert.equal(r.mode,modes[r.block]);});
 const q=quality(rows);
 q.blocks.forEach(r=>{const ref=s.task_blocks.find(x=>x.block===r.block&&x.task_index===r.task_index);
  assert.equal(ref.complete,r.complete);for(const k of ['best','median','sample_sd'])r[k]===null?assert.equal(ref[k],null):same(r[k],ref[k]);});
 q.contrasts.forEach(r=>{const ref=s.contrasts.find(x=>x.repeat===r.repeat&&x.task_index===r.task_index);
  assert.equal(ref.complete,r.complete);for(const k of ['oriented_best_delta','oriented_median_delta'])r[k]===null?assert.equal(ref[k],null):same(r[k],ref[k]);});
 assert.equal(s.overlaps.length,8);
 const pass=Boolean(s.structure&&rows.every(r=>r.valid)&&s.recomputed===16&&q.gate&&s.overlaps.every(x=>x.host_training_envelope_overlap_seconds>0));
 assert.equal(s.predeclared_gate_met,pass);
 console.log(JSON.stringify({passed:true,planned:16,complete:s.complete,valid:s.valid,quality_gate:pass,
  summary_sha256:hashes['summary.json'],plan_sha256:s.plan_sha256,hashes,contrasts:q.contrasts},null,2));
}else console.log(JSON.stringify({selftests:'passed',gpu_calls:0,model_calls:0}));
