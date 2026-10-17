// Independently verify safe-receipt denominators/algebra, NOT raw predictions.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const dir=process.argv[2], raw=fs.readFileSync(`${dir}/closed-output-complementarity-v1.safe.json`);
const hash=crypto.createHash('sha256').update(raw).digest('hex');
assert.equal(hash,'87480e08d6b41edfdf7dc73b7abba9ac351c3eeca50a036d85db2b8252266fd2');
const d=JSON.parse(raw),tasks=['aerial-cactus-identification','denoising-dirty-documents'];
assert.equal(d.assigned_runs,96);assert.equal(d.task_pools,24);assert.equal(d.rows.length,24);
assert.equal(d.source_sha256,'85d8fdc8b81ba56981f8c8620fe25c523f9fbf069f16dab3f9551d6d3a346c36');
assert.equal(new Set(d.rows.map(r=>`${r.job}:${r.block}:${r.task}`)).size,24);
const close=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-12);
const stat=x=>{const v=[...x].sort((a,b)=>a-b),n=v.length,mean=v.reduce((a,b)=>a+b,0)/n;
return {n,median:(v[Math.floor((n-1)/2)]+v[Math.floor(n/2)])/2,sample_sd:Math.sqrt(v.reduce((s,x)=>s+(x-mean)**2,0)/(n-1)),min:v[0],max:v[n-1]};};
for(const r of d.rows){
 assert.ok([18770,18807,18997].includes(r.job)&&r.block>=0&&r.block<4&&tasks.includes(r.task));
 assert.equal(r.assigned_runs,4);assert.equal(r.library_size,r.prediction_hashes.length);
 assert.equal(r.library_size,r.single_scores.length);assert.equal(new Set(r.prediction_hashes).size,r.library_size);
 assert.ok(r.library_size>=1&&r.library_size<=r.timely_valid_candidates+1);
 assert.equal(r.split_group_counts.reduce((a,b)=>a+b,0),r.query_groups);
 const s=r.task===tasks[0]?1:-1,f=r.full_development;
 close(f.best_single,s===1?Math.max(...r.single_scores):Math.min(...r.single_scores));
 close(f.uniform_gain,s*(f.uniform-f.best_single));close(f.oracle_pair_gain,s*(f.oracle_equal_pair-f.best_single));
 assert.equal(r.post_adaptive_resplit_sensitivity.length,2);
 const [a,b]=r.post_adaptive_resplit_sensitivity;assert.equal(a.fit_rows,b.check_rows);assert.equal(b.fit_rows,a.check_rows);
 for(const split of [a,b])for(const m of ['uniform','top2','greedy20'])close(split.gains[m],s*(split.values[m]-split.values.selected_single));
}
const groups=tasks.map(task=>{
 const rows=d.rows.filter(r=>r.task===task);assert.equal(rows.length,12);
 return {task,pools:12,methods:Object.fromEntries(['uniform','top2','greedy20'].map(m=>[m,{
  both_directions_positive:rows.filter(r=>r.post_adaptive_resplit_sensitivity.every(s=>s.gains[m]>1e-12)).length,
  both_directions_nonnegative:rows.filter(r=>r.post_adaptive_resplit_sensitivity.every(s=>s.gains[m]>=-1e-12)).length,
  both_directions_gain_atleast_001:rows.filter(r=>r.post_adaptive_resplit_sensitivity.every(s=>s.gains[m]>=.001)).length,
  worse_direction_gain:stat(rows.map(r=>Math.min(...r.post_adaptive_resplit_sensitivity.map(s=>s.gains[m]))))
 }])),full_development_uniform_positive:rows.filter(r=>r.full_development.uniform_gain>1e-12).length,
 full_development_oracle_equal_pair_positive:rows.filter(r=>r.full_development.oracle_pair_gain>1e-12).length,
 full_development_oracle_equal_pair_gain:stat(rows.map(r=>r.full_development.oracle_pair_gain))};
});
const out={passed:true,receipt_sha256:hash,assigned_runs:96,task_pools:24,
 cpu_host_wall_seconds:d.elapsed_cpu_host_wall_seconds,raw_prediction_recomputation:false,groups,
 limits:['Independent denominator/algebra check, not independent raw prediction/reference extraction.',
 'Two directions share adaptively searched data; not independent repetitions or fresh holdout.',
 '.001 is a descriptive magnitude bin, not a new predeclared success gate; AUC/RMSE never pooled.']};
fs.writeFileSync(`${dir}/independent-summary.json`,JSON.stringify(out,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(out,null,2));
console.log(JSON.stringify(d.rows.map(r=>({job:r.job,block:r.block,task:r.task,library:r.library_size,
 full:r.full_development,split_gains:r.post_adaptive_resplit_sensitivity.map(s=>s.gains)})),null,2));
