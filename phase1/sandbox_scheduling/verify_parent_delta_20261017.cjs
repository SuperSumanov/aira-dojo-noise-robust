// Independent numeric aggregation; not independent reconstruction of raw parents.
const fs=require('fs'),crypto=require('crypto'),assert=require('assert/strict'),path=require('path');
const {verify}=require('./verify_adaptation_lineage_20261017.cjs');
const specs=[
 [18770,'pooling_18770_closed','adaptation-lineage-extension-20261017.safe.json','ce2df3e9c801da6c1a8e407d542f963d61c47d9fcde807c52b15c2308e14e644','7088b473147dfd8cda6ef806f71ae98eac21a366dcb2ae75c548a4711d30fb72',75,32],
 [18807,'colocation_18807_closed','adaptation-lineage-extension-20261017.safe.json','b47201384f5d3c385f471becba37bb2f546747de89a529f55d48f0ff9a264430','602b2034d27cd847bf9379ee457f4d4044c4f5a9a1f089ab33674905669680c3',78,32],
 [18997,'selective_18997_closed','adaptation-lineage-20261017.safe.json','6ec665d244a8cd54820542b175526975d2a13ed24a0185ddd56a7d8dd2d19698','c8d759fa8377e8410df8c26f319ba9c3d4931a2b5a01505b774dde29c481746e',76,32],
 [18412,'metric_deployment_18412_closed','adaptation-lineage-20261017.safe.json','45400a0d57b706268343287a9e0d438e4077b992f13c427e786c394416aba0cc','950bfd757a3502b3c195516297b2664e2fca5ff51083f79cfbbb636198aab918',157,48]];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const tally=rr=>rr.reduce((a,r)=>(a[r.relation]=(a[r.relation]??0)+1,a),{});
const same=(a,b)=>assert.deepEqual(Object.entries(a).sort(),Object.entries(b).sort());
const stats=v=>{if(!v.length)return {n:0,median:null,sample_sd:null};v=[...v].sort((a,b)=>a-b);let mean=v.reduce((a,x)=>a+x,0)/v.length;return {n:v.length,median:(v[Math.floor((v.length-1)/2)]+v[Math.floor(v.length/2)])/2,sample_sd:v.length>1?Math.sqrt(v.reduce((a,x)=>a+(x-mean)**2,0)/(v.length-1)):null};};
const cohorts=[],all=[];
for(const [job,dir,file,lpin,ppin,count,assigned] of specs){
 const full=path.join(__dirname,dir),verified=verify(full,file,lpin,count,assigned),b=fs.readFileSync(path.join(full,'parent-delta-20261017.safe.json'));
 assert.equal(hash(b),ppin);const p=JSON.parse(b),l=JSON.parse(fs.readFileSync(path.join(full,file)));
 assert.equal(p.lineage_sha256,lpin);assert.equal(p.rows.length,count);
 const original=new Map(l.candidates.map(c=>[`${c.index}:${c.candidate}`,c]));
 assert.equal(new Set(p.rows.map(r=>`${r.index}:${r.candidate}`)).size,count);
 for(const r of p.rows){
  const c=original.get(`${r.index}:${r.candidate}`);assert.ok(c);
  for(const k of ['block','task','category','valid','score','pool_elapsed'])assert.equal(r[k],c[k]);
  if(!r.parent_resolved)continue;
  assert.equal(r.new_parent,c.category.endsWith('_from_new'));assert.ok(r.parent_admitted_pool_elapsed>=0&&r.parent_admitted_pool_elapsed<r.pool_elapsed);
  const sign=r.task==='denoising-dirty-documents'?-1:1,gain=r.valid?sign*(r.score-r.parent_score):null;
  if(r.valid)assert.ok(Math.abs(gain-r.gain_vs_parent)<1e-12);else assert.equal(r.gain_vs_parent,null);
  assert.equal(r.relation,gain===null?'invalid':gain>1e-12?'better':gain< -1e-12?'worse':'tie');
 }
 for(const g of p.summary){const rr=p.rows.filter(r=>r.parent_resolved&&r.task===g.task&&r.new_parent===g.new_parent);assert.equal(rr.length,g.returned);same(tally(rr),g.relations);
  for(const [k,values] of [['valid_gain',rr.filter(r=>r.valid).map(r=>r.gain_vs_parent)],['parent_admission_seconds',rr.map(r=>r.parent_admitted_pool_elapsed)]]){
   const s=stats(values);for(const f of ['n','median','sample_sd']){if(s[f]===null)assert.equal(g[k][f],null);else assert.ok(Math.abs(g[k][f]-s[f])<1e-9);}
  }
 }
 const rows=p.rows.map(r=>({job,...r,arm:l.groups.find(g=>g.block===r.block&&g.task===r.task).pool_mode}));all.push(...rows);
 cohorts.push({job,parent_sha256:ppin,lineage:verified,new_parent_returned:rows.filter(r=>r.parent_resolved&&r.new_parent).length,
    new_parent_relations:tally(rows.filter(r=>r.parent_resolved&&r.new_parent))});
}
const summarize=rr=>({returned:rr.length,relations:tally(rr),valid_gain:stats(rr.filter(r=>r.valid).map(r=>r.gain_vs_parent))});
const scheduling=all.filter(r=>r.job!==18412&&r.parent_resolved&&r.new_parent);
const metric=[];
for(const arm of ['old_fast','old_medium','new_medium'])for(const task of ['aerial-cactus-identification','denoising-dirty-documents']){
 const rr=all.filter(r=>r.job===18412&&r.arm===arm&&r.task===task&&r.parent_resolved&&r.new_parent);
 metric.push({arm,task,...summarize(rr),by_block:[...new Set(all.filter(r=>r.job===18412&&r.arm===arm).map(r=>r.block))].sort().map(block=>({block,...summarize(rr.filter(r=>r.block===block))}))});
}
const out={passed:true,cohorts,scheduling_new_parent:{returned:scheduling.length,relations:tally(scheduling),
 by_task:[...new Set(scheduling.map(r=>r.task))].map(task=>({task,...summarize(scheduling.filter(r=>r.task===task))}))},metric_new_parent_by_arm:metric,
 observations:{scheduling_returned:all.filter(r=>r.job!==18412).length,metric_returned:all.filter(r=>r.job===18412).length},
 limits:['Actual admission parent matched to an earlier external DEV receipt in remote reader; numeric aggregation independent, raw linkage not re-extracted.',
 'Post-treatment parent states and late admission differ. Do not call conditional yields model effects or pool them as independent replications.',
 'Metric48 uses30minutes, other cohorts17minutes: no causal budget contrast, no combined rate. AUC/RMSE gains are never pooled.',
 'Returned-only denominator retains invalid returns but omits censored attempts with no return. No main gate changes.']};
console.log(JSON.stringify(out,null,2));
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(out,null,2)+'\n',{flag:'wx'});
