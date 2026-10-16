const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const dir=process.argv[2];assert.ok(dir);
const raw=fs.readFileSync(`${dir}/quota-borrowing-20261017-v1.safe.json`),r=JSON.parse(raw);
const old=JSON.parse(fs.readFileSync(`${dir}/bottleneck-20261016-v1.safe.json`));
assert.equal(r.plan_sha256,old.plan_sha256);assert.equal(r.pools.length,4);
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-5);
const pools=r.pools.map(p=>{
 let wall=0,slots=0,wait=0,total=0;const byTask=[0,0];
 for(const s of p.states){
  assert.ok(s.seconds>=0&&Number.isFinite(s.seconds));
  assert.equal(s.active.length,2);assert.equal(s.waiting.length,2);
  s.active.forEach(v=>assert.ok(Number.isInteger(v)&&v>=0&&v<=2));
  s.waiting.forEach(v=>assert.ok(Number.isInteger(v)&&v>=0));
  const spare=4-s.active[0]-s.active[1];let blocked=0;
  for(let i=0;i<2;i++)if(s.active[i]===2){blocked+=s.waiting[i];if(spare>0&&s.waiting[i]>0)byTask[i]+=s.seconds;}
  if(spare>0&&blocked>0){wall+=s.seconds;slots+=Math.min(spare,blocked)*s.seconds;}
  wait+=(s.waiting[0]+s.waiting[1])*s.seconds;total+=s.seconds;
 }
 close(total,p.reserved_seconds);close(wall,p.borrowable_wall_seconds);close(slots,p.borrowable_permit_seconds);
 close(wait,p.waiting_seconds);close(wait,old.pools[p.block].generation.waiting_seconds);
 return {block:p.block,borrowable_wall_seconds:wall,fraction:wall/total,borrowable_permit_seconds:slots,
  task_wall_seconds:{aerial:byTask[0],denoise:byTask[1]}};
});
const result={passed:true,source_sha256:crypto.createHash('sha256').update(raw).digest('hex'),pools,
 boundary:'Independent integration of binned observed state durations, not independent event parsing, causal saved time or quality.'};
fs.writeFileSync(`${dir}/quota-borrowing-independent.json`,JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));
