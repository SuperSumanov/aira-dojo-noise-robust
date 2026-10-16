const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const file=process.argv[2];assert.ok(file);const raw=fs.readFileSync(file),r=JSON.parse(raw);
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-5);
const out=[];for(const p of r.pools){
 near(p.segments.reduce((a,s)=>a+s.seconds,0),p.observed_borrowable_wall_seconds);
 const checks=[];for(const expected of p.by_slack){
  const h=expected.minimum_remaining_seconds;let wall=0,permits=0,requests=0;const roles={draft:0,improve:0,debug:0,analyze:0};
  for(const s of p.segments){
   assert.ok(Number.isFinite(s.seconds)&&s.seconds>0&&Number.isInteger(s.spare)&&s.spare>=1&&s.spare<=4);
   const durations=s.blocked.map(q=>{assert.ok(q.role in roles);const x=Math.max(0,Math.min(s.seconds,q.slack_at_start-h));roles[q.role]+=x;return x;}).sort((a,b)=>b-a);
   // Top spare lifetimes integrate min(spare, eligible requests) without the
   // Python implementation's interval subdivision.
   wall+=durations[0]||0;permits+=durations.slice(0,s.spare).reduce((a,b)=>a+b,0);requests+=durations.reduce((a,b)=>a+b,0);
  }
  near(wall,expected.wall);near(permits,expected.permits);near(requests,expected.requests);
  Object.keys(roles).forEach(k=>near(roles[k],expected.request_seconds_by_role[k]));
  checks.push({minimum_remaining_seconds:h,wall,permits,requests,request_seconds_by_role:roles});
 }
 out.push({block:p.block,observed_borrowable_wall_seconds:p.observed_borrowable_wall_seconds,by_slack:checks});
}
const result={passed:true,sha256:crypto.createHash('sha256').update(raw).digest('hex'),pools:out};
if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2),{flag:'wx'});
console.log(JSON.stringify(result,null,2));
