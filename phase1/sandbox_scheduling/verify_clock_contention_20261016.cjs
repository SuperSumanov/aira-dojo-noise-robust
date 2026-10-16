// Independent aggregate/denominator check. NOT an independent DEV scorer.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const near=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-12);
const median2=v=>(v[0]+v[1])/2;
function effect(rows,p){
 const r=rows.filter(x=>x.program===p);
 if(r.length!==4||r.some(x=>!x.complete||!x.valid||x.score==null||x.steps==null))return {program:p,complete:false};
 const a=r.filter(x=>x.mode==='solo'),b=r.filter(x=>x.mode==='colocated');
 assert.equal(a.length,2);assert.equal(b.length,2);
 const av=a.map(x=>x.score*(p===0?1:-1)),bv=b.map(x=>x.score*(p===0?1:-1));
 const as=a.map(x=>x.steps),bs=b.map(x=>x.steps);
 return {program:p,complete:true,solo_steps:as,colocated_steps:bs,solo_scores:a.map(x=>x.score),colocated_scores:b.map(x=>x.score),
   median_step_delta:median2(bs)-median2(as),oriented_mean_score_delta:median2(bv)-median2(av),
   all_colocated_steps_lower:Math.max(...bs)<Math.min(...as),all_colocated_scores_worse:Math.max(...bv)<Math.min(...av),
   all_colocated_scores_better:Math.min(...bv)>Math.max(...av),solo_score_repeat_span:Math.max(...av)-Math.min(...av),
   colocated_score_repeat_span:Math.max(...bv)-Math.min(...bv)};
}
const fixture=Array.from({length:8},(_,i)=>({program:i%2,mode:['solo','colocated','colocated','solo'][Math.floor(i/2)],
 complete:true,valid:true,steps:[100,70,70,100][Math.floor(i/2)],score:i%2?[.02,.03,.03,.02][Math.floor(i/2)]:[.9,.8,.8,.9][Math.floor(i/2)]}));
assert.ok(effect(fixture,0).all_colocated_scores_worse);assert.ok(effect(fixture,1).all_colocated_scores_worse);
fixture[0].valid=false;assert.equal(effect(fixture,0).complete,false);
if(process.argv[2]){
 const dir=process.argv[2],hashes={};
 const read=n=>{const raw=fs.readFileSync(`${dir}/${n}`);hashes[n]=crypto.createHash('sha256').update(raw).digest('hex');return JSON.parse(raw);};
 const rows=read('runs.json'),s=read('summary.json'),diffs=read('prediction-differences.json');
 assert.equal(rows.length,8);assert.equal(new Set(rows.map(r=>r.index)).size,8);
 for(const r of rows){assert.equal(r.program,r.index%2);assert.equal(r.block,Math.floor(r.index/2));
   assert.equal(r.mode,['solo','colocated','colocated','solo'][r.block]);assert.equal(r.repeat,Math.floor(r.block/2));}
 assert.equal(s.complete,rows.filter(r=>r.complete).length);assert.equal(s.valid,rows.filter(r=>r.valid).length);
 assert.ok(s.gpu_seconds>0&&s.gpu_seconds<=2700);near(s.gpu_hours,s.gpu_seconds/3600);
 for(let p=0;p<2;p++){
   const actual=effect(rows,p),expected=s.effects.find(r=>r.program===p);
   assert.deepEqual(Object.keys(actual).sort(),Object.keys(expected).sort());
   for(const [k,v]of Object.entries(actual))typeof v==='number'?near(v,expected[k]):assert.deepEqual(v,expected[k]);
   const selected=rows.filter(r=>r.program===p);assert.equal(new Set(selected.map(r=>r.seed)).size,1);
   assert.ok(new Set(selected.map(r=>r.executed_code_sha256).filter(Boolean)).size<=1);
 }
 for(const d of diffs){assert.equal(d.program,d.a%2);assert.equal(d.a%2,d.b%2);
   assert.equal(d.same_mode,rows[d.a].mode===rows[d.b].mode);assert.ok(d.mean_abs_diff>=0&&d.max_abs_diff>=d.mean_abs_diff);
   if(d.same_bytes){near(d.max_abs_diff,0);near(d.mean_abs_diff,0);}}
 console.log(JSON.stringify({passed:true,rows:8,complete:s.complete,independent_rescoring:false,hashes}));
}else console.log(JSON.stringify({self_tests:true}));
