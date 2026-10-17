// Descriptive robustness check over three already closed cohorts. No scores recomputed.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {verify}=require('./verify_adaptation_lineage_20261017.cjs');
const specs=[
 [18770,'pooling_18770_closed','adaptation-lineage-extension-20261017.safe.json','ce2df3e9c801da6c1a8e407d542f963d61c47d9fcde807c52b15c2308e14e644',75],
 [18807,'colocation_18807_closed','adaptation-lineage-extension-20261017.safe.json','b47201384f5d3c385f471becba37bb2f546747de89a529f55d48f0ff9a264430',78],
 [18997,'selective_18997_closed','adaptation-lineage-20261017.safe.json','6ec665d244a8cd54820542b175526975d2a13ed24a0185ddd56a7d8dd2d19698',76]];
const verified=[],rows=[],cc=[];
for(const [job,dir,file,pin,n] of specs){
 const full=path.join(__dirname,dir);verified.push({job,...verify(full,file,pin,n)});
 const d=JSON.parse(fs.readFileSync(path.join(full,file)));
 rows.push(...d.groups.map(g=>({job,...g})));cc.push(...d.candidates.map(c=>({job,...c})));
}
const count=x=>x.reduce((a,c)=>(a[c.category]=(a[c.category]??0)+1,a),{});
const byTask=[];
for(const task of [...new Set(rows.map(x=>x.task))]){
 const rr=rows.filter(x=>x.task===task),c=cc.filter(x=>x.task===task),v=c.filter(x=>x.valid);
 assert.equal(rr.length,12);
 byTask.push({task,pools:rr.length,returned:c.length,valid:v.length,unresolved:c.filter(x=>!x.lineage_resolved).length,
  returned_categories:count(c),valid_categories:count(v),
  pool_gains_after_first:rr.filter(x=>x.oriented_gain_after_first_attempts>1e-12).length,
  pool_winner_from_new:rr.filter(x=>x.winning_categories.some(k=>k.endsWith('_from_new'))).length,
  pool_winner_debug:rr.filter(x=>x.winning_categories.some(k=>k.startsWith('debug_'))).length,
  pool_later_gains_with_no_valid_first:rr.filter(x=>x.oriented_gain_after_first_attempts>1e-12&&x.first_attempt_valid===0).length,
  pool_later_gains_but_no_first_gain:rr.filter(x=>x.oriented_gain_after_first_attempts>1e-12&&Math.abs(x.first_attempt_only_observed_best-x.initial)<1e-12).length});
}
const out={schema:1,passed:true,verifier_sha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
 verified,assigned:verified.reduce((a,x)=>a+x.assigned,0),returned:cc.length,valid:cc.filter(x=>x.valid).length,
 unresolved:cc.filter(x=>!x.lineage_resolved).length,task_pools:rows.length,
 pools_later_gain:rows.filter(x=>x.oriented_gain_after_first_attempts>1e-12).length,
 pools_new_parent_winner:rows.filter(x=>x.winning_categories.some(k=>k.endsWith('_from_new'))).length,
 debug_valid:cc.filter(x=>x.valid&&x.category.startsWith('debug_')).length,by_task:byTask,
 limits:['Repeated two tasks and different policies: 24 task-pools are not 24 independent task replications.',
 'Fixed reverse-order blocks with paired seeds are not randomized treatment assignments.',
 'Post-hoc lineage/subset associations cannot identify a causal benefit of new-parent refinement or repair priority.',
 'No use of invalid19004 outcomes. No new scoring. Raw journal linkage not independently re-extracted.',
 'Do not optimize a new policy using these same DEV endpoints and claim confirmatory generalization.']};
console.log(JSON.stringify(out,null,2));
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(out,null,2)+'\n',{flag:'wx'});
