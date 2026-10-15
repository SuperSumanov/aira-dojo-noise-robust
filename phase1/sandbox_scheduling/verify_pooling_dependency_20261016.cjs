// Independent event-driven implementation; does not import the Python model.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);
function replay(jobs,mode,overhead=0){
 const groups=new Map();jobs.forEach((j,i)=>{if(!groups.has(j.session))groups.set(j.session,[]);groups.get(j.session).push({...j,i});});
 const list=[];
 for(const [sid,g] of groups){g.sort((a,b)=>a.arrival-b.arrival);g.forEach((j,k)=>{j.gap=k?j.arrival-g[k-1].original_start-g[k-1].duration:j.arrival;assert.ok(j.gap>=0);});list.push({kind:'ready',time:g[0].gap,sid,k:0});}
 let waiting=[],active=new Map(),out=[],t=0;
 while(list.length||waiting.length){
  list.sort((a,b)=>a.time-b.time||(a.kind==='done'?-1:1));assert.ok(list.length);t=list[0].time;
  while(list.length&&list[0].time<=t){
   const e=list.shift();
   if(e.kind==='ready')waiting.push(e);
   else {active.delete(e.device);const next=groups.get(e.sid)[e.k+1];if(next)list.push({kind:'ready',time:e.time+next.gap,sid:e.sid,k:e.k+1});}
   list.sort((a,b)=>a.time-b.time||(a.kind==='done'?-1:1));
  }
  waiting.sort((a,b)=>a.time-b.time||a.sid-b.sid||a.k-b.k);
  for(let pos=0;pos<waiting.length;){
   const e=waiting[pos],j=groups.get(e.sid)[e.k];
   const eligible=mode==='unlimited'?[e.sid]:mode==='fixed'?[j.lane]:[0,1,2,3];
   const device=eligible.find(d=>!active.has(d));
   if(device===undefined){if(mode==='shared')break;pos++;continue;}
   waiting.splice(pos,1);const end=t+j.duration+overhead;active.set(device,e.sid);
   out.push({end,wait:t-e.time,task:j.task,deadline:j.deadline,index:j.i});list.push({...e,kind:'done',time:end,device});
  }
 }
 assert.equal(out.length,jobs.length);return out;
}
const path=process.argv[2],result=JSON.parse(fs.readFileSync(path));let cases=0;
const root=require('path').dirname(path);
for(const s of result.sources){
 const raw=fs.readFileSync(`${root}/${s.file}`);assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),s.sha256);
 const d=JSON.parse(raw);
 for(const p of s.pools){
  const jobs=d.pools.find(x=>x.block===p.block).jobs;
  for(const [mode,extra,ref] of [...['fixed','shared','unlimited'].map(m=>[m,0,p.scenarios[m]]),...p.shared_overhead.map(x=>['shared',x.seconds,x])]){
   const out=replay(jobs,mode,extra);close(out.reduce((a,r)=>a+r.wait,0),ref.wait_seconds);
   assert.equal(out.filter(r=>r.end<=r.deadline).length,ref.released_by_deadline);
   for(const task of [0,1])assert.equal(out.filter(r=>r.task===task&&r.end<=r.deadline).length,ref.task_counts[String(task)]);
   cases++;
  }
 }
}
console.log(JSON.stringify({passed:true,independent_scenarios:cases,quality_claim:false,gpu_calls:0}));
