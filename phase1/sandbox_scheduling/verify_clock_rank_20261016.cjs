// Independent numeric/denominator verification, NOT independent DEV regrading.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const near=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-12);
function ranks(rows,t){
 const r=rows.filter(x=>Math.floor(x.program/2)===t);
 if(r.length!==8||r.some(x=>!x.complete||!x.valid||x.score==null))return {task_index:t,complete:false};
 const sign=t===0?1:-1,margins=[];
 for(let b=0;b<4;b++){
  const pair=r.filter(x=>x.block===b).sort((a,b)=>a.program-b.program);assert.equal(pair.length,2);
  margins.push(sign*(pair[0].score-pair[1].score));
 }
 const order={};
 for(const mode of ['solo','colocated']){
  const a=r.filter(x=>x.mode===mode&&x.program===2*t).map(x=>sign*x.score);
  const b=r.filter(x=>x.mode===mode&&x.program===2*t+1).map(x=>sign*x.score);
  assert.equal(a.length,2);assert.equal(b.length,2);
  order[mode]=Math.min(...a)>Math.max(...b)?1:Math.max(...a)<Math.min(...b)?-1:0;
 }
 return {task_index:t,complete:true,block_oriented_first_minus_second:margins,
  within_repeat_flip:[Math.sign(margins[0])*Math.sign(margins[1])===-1,Math.sign(margins[3])*Math.sign(margins[2])===-1],
  solo_same_order:Math.sign(margins[0])===Math.sign(margins[3])&&margins[0]!==0,
  colocated_same_order:Math.sign(margins[1])===Math.sign(margins[2])&&margins[1]!==0,
  interval_separated_order:order,strict_repeated_flip:order.solo*order.colocated===-1};
}
const fixture=Array.from({length:16},(_,i)=>({index:i,block:Math.floor(i/4),program:i%4,complete:true,valid:true,
 mode:['solo','colocated','colocated','solo'][Math.floor(i/4)],score:i%2?.8:([0,3].includes(Math.floor(i/4))?.9:.7)}));
assert.equal(ranks(fixture,0).strict_repeated_flip,true);assert.equal(ranks(fixture,1).strict_repeated_flip,true);
fixture[0].complete=false;assert.equal(ranks(fixture,0).complete,false);
if(process.argv[2]){
 const dir=process.argv[2],hashes={};
 const read=n=>{const b=fs.readFileSync(`${dir}/${n}`);hashes[n]=crypto.createHash('sha256').update(b).digest('hex');return JSON.parse(b);};
 const rows=read('runs.json'),s=read('summary.json');assert.equal(rows.length,16);
 assert.deepEqual(rows.map(x=>x.index),Array.from({length:16},(_,i)=>i));
 for(const r of rows){assert.equal(r.block,Math.floor(r.index/4));assert.equal(r.program,r.index%4);
  assert.equal(r.mode,['solo','colocated','colocated','solo'][r.block]);assert.equal(r.repeat,Math.floor(r.block/2));}
 assert.equal(s.complete,rows.filter(x=>x.complete).length);assert.equal(s.valid,rows.filter(x=>x.valid).length);
 assert.ok(s.gpu_seconds>0&&s.gpu_seconds<=5400);near(s.gpu_hours,s.gpu_seconds/3600);
 for(let t=0;t<2;t++)assert.deepEqual(ranks(rows,t),s.ranking.find(x=>x.task_index===t));
 for(let p=0;p<4;p++){
  const r=rows.filter(x=>x.program===p),e=s.effects.find(x=>x.program===p);
  assert.equal(new Set(r.map(x=>x.seed)).size,1);assert.ok(new Set(r.map(x=>x.executed_code_sha256).filter(Boolean)).size<=1);
  if(e.complete){const a=r.filter(x=>x.mode==='solo'),b=r.filter(x=>x.mode==='colocated');
   assert.deepEqual(e.solo_steps,a.map(x=>x.steps));assert.deepEqual(e.colocated_steps,b.map(x=>x.steps));
   assert.deepEqual(e.solo_scores,a.map(x=>x.score));assert.deepEqual(e.colocated_scores,b.map(x=>x.score));
   near(e.oriented_mean_score_delta,(p<2?1:-1)*((b[0].score+b[1].score-a[0].score-a[1].score)/2));}
 }
 console.log(JSON.stringify({passed:true,rows:16,complete:s.complete,hashes,independent_rescoring:false}));
}else console.log(JSON.stringify({self_tests:true}));
