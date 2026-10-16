// Descriptive request timing only. No outcome-derived threshold or success gate.
// Frozen before quota search; completed/cancelled requests remain separate.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const MODES=['partitioned','pooled','pooled','partitioned'];
function timing(events){
 const requests=new Map(),active=new Set();let last=-Infinity;
 for(const e of events){
  assert.ok(Number.isFinite(e.time)&&e.time>=last);last=e.time;
  if(e.event==='queued'){
   const r=e.request;assert.ok(!requests.has(r.key));
   requests.set(r.key,{task:r.task,role:r.role,queued:e.time});
  }else{
   const r=requests.get(e.key);assert.ok(r);
   if(e.event==='admitted'){
    assert.equal(r.admitted,undefined);assert.equal(r.cancelled,undefined);
    r.borrowed=[...active].filter(k=>requests.get(k).task===r.task).length>=2;
    r.admitted=e.time;active.add(e.key);assert.ok(active.size<=4);
   }else if(e.event==='released'){
    assert.ok(active.delete(e.key));r.released=e.time;
   }else if(e.event==='cancelled'){
    assert.equal(r.admitted,undefined);assert.equal(r.cancelled,undefined);r.cancelled=e.time;
   }else throw Error('unknown event');
  }
 }
 assert.equal(active.size,0);
 const groups=new Map();
 for(const r of requests.values()){
  assert.ok(r.released!==undefined||r.cancelled!==undefined);
  const key=JSON.stringify([r.task,r.role]);
  if(!groups.has(key))groups.set(key,{task:r.task,role:r.role,queued:0,released:0,cancelled:0,borrowed:0,
   admitted_wait_seconds:0,cancelled_wait_seconds:0,active_request_seconds:0,borrowed_request_seconds:0,waits:[],durations:[]});
  const g=groups.get(key);g.queued++;
  if(r.cancelled!==undefined){g.cancelled++;g.cancelled_wait_seconds+=r.cancelled-r.queued;}
  else{
   const wait=r.admitted-r.queued,duration=r.released-r.admitted;assert.ok(wait>=0&&duration>=0);
   g.released++;g.admitted_wait_seconds+=wait;g.active_request_seconds+=duration;
   g.waits.push(wait);g.durations.push(duration);
   if(r.borrowed){g.borrowed++;g.borrowed_request_seconds+=duration;}
  }
 }
 const median=a=>{if(!a.length)return null;a.sort((x,y)=>x-y);return (a[Math.floor(a.length/2)]+a[Math.floor((a.length-1)/2)])/2;};
 return [...groups.values()].map(({waits,durations,...g})=>({...g,wait_median:median(waits),request_duration_median:median(durations)}));
}
function tests(){
 const e=[],q=(key,task,role,time)=>e.push({event:'queued',request:{key,task,role},time}),a=(key,time)=>e.push({event:'admitted',key,time}),z=(key,time)=>e.push({event:'released',key,time});
 q('a','A','analyze',0);a('a',1);q('b','A','debug',2);a('b',3);q('c','A','analyze',4);a('c',5);
 q('d','B','improve',6);e.push({event:'cancelled',key:'d',time:7});z('a',8);z('b',9);z('c',10);
 const rows=timing(e),an=rows.find(r=>r.task==='A'&&r.role==='analyze');
 assert.equal(an.borrowed,1);assert.equal(an.active_request_seconds,12);assert.equal(an.borrowed_request_seconds,5);assert.equal(an.wait_median,1);
 assert.equal(rows.find(r=>r.task==='B').cancelled_wait_seconds,1);
 assert.throws(()=>timing(e.slice(0,-1)));assert.throws(()=>timing([...e,{event:'released',key:'a',time:11}]));
}
tests();
if(process.argv[2]){
 const dir=process.argv[2],hashes={},rows=[];
 for(let b=0;b<4;b++){
  const name=`generation-${b}.json`,raw=fs.readFileSync(`${dir}/${name}`);
  hashes[name]=crypto.createHash('sha256').update(raw).digest('hex');
  rows.push(...timing(JSON.parse(raw)).map(r=>({block:b,quota_mode:MODES[b],...r})));
 }
 console.log(JSON.stringify({schema:1,purpose:'descriptive role timing; not a success test',hashes,rows,
  limitations:['Request seconds sum overlapping model calls, not saved wall time or GPU cost.','Release includes failed/interrupted requests; not proof of successful generation.','Borrowed marks occupancy at admission, not a partitioned counterfactual.','Cancelled waiting stays separate; no survivor-only denominator.','Known two-task shared-service exploration; timing is not final-quality benefit.']},null,2));
}else console.log(JSON.stringify({selftests:'passed',gpu_calls:0,model_calls:0}));
