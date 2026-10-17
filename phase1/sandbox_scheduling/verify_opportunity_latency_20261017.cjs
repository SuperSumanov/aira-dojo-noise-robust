// Independent numeric checks, not an independent raw event/journal extractor.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const b=fs.readFileSync(path.join(__dirname,'opportunity-latency-20261017.safe.json'));
assert.equal(sha(b),'37b2e5e59e18effce67a33ee2bccfbf772d3ed2e8ff2b684c91e316ac600bee4');
const p=JSON.parse(b),dirs={18770:'pooling_18770_closed',18807:'colocation_18807_closed',18997:'selective_18997_closed'};
const stats=v=>{v=[...v].sort((a,b)=>a-b);if(!v.length)return {n:0,median:null,sample_sd:null};const mean=v.reduce((a,x)=>a+x,0)/v.length;
 return {n:v.length,median:(v[Math.floor((v.length-1)/2)]+v[Math.floor(v.length/2)])/2,sample_sd:v.length>1?Math.sqrt(v.reduce((a,x)=>a+(x-mean)**2,0)/(v.length-1)):null};};
const all=[];
for(const c of p.cohorts){
 const pb=fs.readFileSync(path.join(__dirname,dirs[c.job],'proposal-opportunities-20261017.safe.json'));
 assert.equal(sha(pb),c.proposal_sha256);const proposal=JSON.parse(pb);
 assert.equal(proposal.lineage_sha256,c.lineage_sha256);assert.equal(c.rows.length,proposal.all_admitted_improve);
 const expected=new Map(proposal.rows.map(r=>[`${r.block}:${r.request_key}`,r]));
 for(const r of c.rows){
  const key=`${r.block}:${r.request_key}`,o=expected.get(key);assert.ok(o);expected.delete(key);
  for(const k of ['index','block','task','arm','new_parent','generated','remaining_seconds'])assert.equal(r[k],o[k]);
  assert.equal(r.returned_family,o.returns.length>0);
  assert.ok(r.wait_seconds>=0&&r.admitted_to_release_seconds>=0);
  if(r.generated)assert.ok(r.admitted_to_code_seconds>=0&&r.admitted_to_code_seconds<=r.admitted_to_release_seconds);
  else assert.equal(r.admitted_to_code_seconds,null);
  if(r.returned_family){assert.ok(r.code_to_first_return_seconds>=0);
   assert.ok(Math.abs(r.admitted_to_code_seconds+r.code_to_first_return_seconds-r.admitted_to_first_return_seconds)<1e-6);
   assert.ok(r.admitted_to_first_return_seconds<=r.remaining_seconds+1e-6);
  }else{assert.equal(r.code_to_first_return_seconds,null);assert.equal(r.admitted_to_first_return_seconds,null);}
  all.push({job:c.job,...r});
 }
 assert.equal(expected.size,0);
}
for(const summary of p.summary){
 const rows=all.filter(r=>r.new_parent===summary.new_parent);
 assert.equal(rows.length,summary.admitted);assert.equal(rows.filter(r=>r.generated).length,summary.generated);
 assert.equal(rows.filter(r=>r.returned_family).length,summary.returned_families);
 for(const [key,actual]of Object.entries(summary.timings)){
  const s=stats(rows.map(r=>r[key]).filter(x=>x!==null));
  for(const field of ['n','median','sample_sd']){if(s[field]===null)assert.equal(actual[field],null);else assert.ok(Math.abs(s[field]-actual[field])<1e-9);}
 }
}
const rr=all.filter(r=>r.new_parent),wait=rr.map(r=>r.wait_seconds).sort((a,b)=>a-b);
const out={passed:true,source_sha256:sha(b),assigned_admissions:all.length,new_parent_admissions:rr.length,
 new_parent_wait:{...stats(wait),p90_nearest_rank:wait[Math.ceil(wait.length*.9)-1],max:wait.at(-1),
  above1second:wait.filter(x=>x>1).length,above30seconds:wait.filter(x=>x>30).length},
 by_cohort:p.cohorts.map(c=>({job:c.job,new_parent_wait:stats(c.rows.filter(r=>r.new_parent).map(r=>r.wait_seconds))})),
 scope:'Independent counts/timing algebra only. Raw event extraction not repeated.',
 interpretation:'Observed own-request queue wait is usually small. Earlier upstream generation may still change parent availability, so this does not refute quota pooling or predict saved time/quality.',
 limitations:p.limits};
console.log(JSON.stringify(out,null,2));
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(out,null,2)+'\n',{flag:'wx'});
