// Independent aggregation only: original journal/code linkage is not re-extracted.
const fs=require('fs'),crypto=require('crypto'),assert=require('assert/strict');
function verify(dir,filename,pin,count,assigned=32){
assert.ok(dir);const hashes={};
const read=n=>{const b=fs.readFileSync(`${dir}/${n}`);hashes[n]=crypto.createHash('sha256').update(b).digest('hex');return JSON.parse(b);};
const r=read(filename),runs=read('runs.json'),summary=read('summary.json');
assert.equal(hashes[filename],pin);
assert.equal(hashes['summary.json'],r.summary_sha256);assert.equal(r.candidates.length,count);assert.equal(runs.length,assigned);
assert.equal(r.assigned,assigned);assert.equal(r.groups.length,assigned/4);
const tally=x=>x.reduce((a,c)=>(a[c.category]=(a[c.category]??0)+1,a),{});
const checkMap=(a,b)=>assert.deepEqual(Object.entries(a).sort(),Object.entries(b).sort());
let newParents=0,newParentValid=0,debugValid=0;const results=[];
for(const g of r.groups){
 const cc=r.candidates.filter(c=>c.block===g.block&&c.task===g.task),valid=cc.filter(c=>c.valid),rr=runs.filter(x=>x.block===g.block&&x.task===g.task);
 const s=g.task==='denoising-dirty-documents'?-1:1;
 assert.equal(rr.length,4);assert.equal(cc.length,rr.reduce((a,x)=>a+x.candidate_returns,0));assert.equal(valid.length,rr.reduce((a,x)=>a+x.valid_returns,0));
 assert.equal(new Set(cc.map(c=>`${c.index}:${c.candidate}`)).size,cc.length);
 checkMap(tally(cc),g.returned_categories);checkMap(tally(valid),g.valid_categories);
 const first=Math.max(s*g.initial,...valid.filter(c=>c.first_attempt).map(c=>s*c.score));
 const best=Math.max(s*g.initial,...valid.map(c=>s*c.score));
 assert.ok(Math.abs(first-s*g.first_attempt_only_observed_best)<1e-12);assert.ok(Math.abs(best-s*g.final_best)<1e-12);
 assert.ok(Math.abs(best-first-g.oriented_gain_after_first_attempts)<1e-12);
 const ref=summary.by_pool.find(x=>x.block===g.block&&x.task===g.task);assert.equal(g.final_best,ref.best);
 let record=s*g.initial;const increments=[];
 for(const c of [...valid].sort((a,b)=>a.pool_elapsed-b.pool_elapsed||a.index-b.index||a.candidate-b.candidate)){
  const gain=s*c.score-record;if(gain>1e-12){increments.push({index:c.index,candidate:c.candidate,category:c.category,gain});record=s*c.score;}
 }
 assert.equal(increments.length,g.pool_record_events.length);
 increments.forEach((x,i)=>{const y=g.pool_record_events[i];for(const k of ['index','candidate','category'])assert.equal(x[k],y[k]);assert.ok(Math.abs(x.gain-y.gain)<1e-12);});
 newParents+=cc.filter(c=>c.category.endsWith('_from_new')).length;newParentValid+=valid.filter(c=>c.category.endsWith('_from_new')).length;
 debugValid+=valid.filter(c=>c.category.startsWith('debug_')).length;
 results.push({block:g.block,task:g.task,valid:valid.length,record_events:increments.length,
   gain_after_first_attempts:g.oriented_gain_after_first_attempts,winning_categories:g.winning_categories});
}
const out={passed:true,hashes,assigned,returned:r.candidates.length,valid:r.candidates.filter(c=>c.valid).length,
 unresolved:r.candidates.filter(c=>!c.lineage_resolved).length,new_parent_descendant_returns:newParents,
 new_parent_descendant_valid:newParentValid,debug_valid:debugValid,task_pools:r.groups.length,
 task_pools_gain_after_first_attempts:results.filter(x=>x.gain_after_first_attempts>1e-12).length,results,
 limitations:['Independent counts/chronological records/endpoints and transferSHA; not independent raw journal linkage.',
 'Observed first-attempt subset is not a new no-feedback strategy. No causal allocation gain or independent task generalization.']};
return out;
}
module.exports={verify};
if(require.main===module) console.log(JSON.stringify(verify(process.argv[2],
 'adaptation-lineage-20261017.safe.json','6ec665d244a8cd54820542b175526975d2a13ed24a0185ddd56a7d8dd2d19698',76),null,2));
