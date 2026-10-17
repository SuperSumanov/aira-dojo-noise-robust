// Local independent aggregation, optional remote raw-event timing cross-check.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const specs=[
 [18770,'pooling_18770_closed','scheduling-pooling-20261016-v3','adaptation-lineage-extension-20261017.safe.json','239068967985e3a3b6edacae54c0d6c41bb305a89679c986de2577eca933f322',60,75,32],
 [18807,'colocation_18807_closed','scheduling-colocation-20261016-v1','adaptation-lineage-extension-20261017.safe.json','0be079dbf6a1e3d0d1773032b4725dc07cae59145e8b91b6f53d1c60ea934c83',69,78,32],
 [18997,'selective_18997_closed','scheduling-selective-20261017-v1','adaptation-lineage-20261017.safe.json','b207d27b0ae4f4083d5352c4ded9d6c867bde40267b06f826f8de4a11a686db0',66,76,32],
 [18412,'metric_deployment_18412_closed','scheduling-metric-deployment-20261015-v2','adaptation-lineage-20261017.safe.json','2f5cfaea084579f5d467f38a8ad5738e9ac9ad0f4780e9c6a31aef3b80a14803',121,157,48]
];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const raw=process.argv.includes('--raw-events'),bands=['under300','300to600','600to900','atleast900'];
const band=x=>x<300?bands[0]:x<600?bands[1]:x<900?bands[2]:bands[3];
const stats=v=>{if(!v.length)return {n:0,median:null,sample_sd:null};v=[...v].sort((a,b)=>a-b);let mean=v.reduce((a,x)=>a+x,0)/v.length;return {n:v.length,median:(v[Math.floor((v.length-1)/2)]+v[Math.floor(v.length/2)])/2,sample_sd:v.length>1?Math.sqrt(v.reduce((a,x)=>a+(x-mean)**2,0)/(v.length-1)):null};};
const summarize=rr=>({admitted:rr.length,generated:rr.filter(r=>r.generated).length,with_linked_returns:rr.filter(r=>r.returns.length).length,
 with_linked_valid_returns:rr.filter(r=>r.has_valid_return).length,with_linked_improvement:rr.filter(r=>r.improved_parent).length,
 remaining:stats(rr.map(r=>r.remaining_seconds))});
const cohorts=[],all=[];let unresolvedValid=0;
for(const [job,dir,remote,file,pin,count,total,assigned]of specs){
 const root=raw?path.join('/research/d7/spc/yzyang4',remote):path.join(__dirname,dir);
 const b=fs.readFileSync(path.join(root,'proposal-opportunities-20261017.safe.json'));assert.equal(hash(b),pin);const p=JSON.parse(b);
 const lb=fs.readFileSync(path.join(root,file));assert.equal(hash(lb),p.lineage_sha256);const l=JSON.parse(lb);
 assert.equal(p.all_admitted_improve,count);assert.equal(p.rows.length,count);assert.equal(p.assigned,assigned);
 assert.equal(p.matched_returns+p.unresolved_returns.length,total);
 assert.equal(new Set(p.rows.map(r=>`${r.block}:${r.request_key}`)).size,count);
 const originals=new Map(l.candidates.map(c=>[`${c.index}:${c.candidate}`,c])),seen=new Set();
 for(const r of p.rows){
  assert.equal(r.remaining_band,band(r.remaining_seconds));assert.ok(r.remaining_seconds>0&&r.remaining_seconds<=p.run_seconds);
  assert.ok(Math.abs(r.admitted_run_elapsed+r.remaining_seconds-p.run_seconds)<1e-9);
  let gains=[];for(const c of r.returns){
   const key=`${r.index}:${c.candidate}`;assert.ok(!seen.has(key));seen.add(key);
   const src=originals.get(key);assert.ok(src);assert.equal(src.task,r.task);assert.equal(src.valid,c.valid);
   assert.equal(src.score,c.score);assert.equal(src.category,c.category);assert.equal(r.new_parent,c.category.endsWith('_from_new'));
   if(c.valid){const gain=(r.task==='denoising-dirty-documents'?-1:1)*(c.score-r.parent_score);assert.ok(Math.abs(gain-c.gain_vs_parent)<1e-12);gains.push(gain);}else assert.equal(c.gain_vs_parent,null);
  }
  assert.equal(r.has_valid_return,gains.length>0);assert.equal(r.improved_parent,gains.length>0&&Math.max(...gains)>1e-12);
  assert.equal(r.best_gain_vs_parent,gains.length?Math.max(...gains):null);
 }
 for(const c of p.unresolved_returns){const key=`${c.index}:${c.candidate}`;assert.ok(!seen.has(key)&&originals.has(key));seen.add(key);}
 assert.equal(seen.size,total);
 const uv=p.unresolved_returns.filter(c=>originals.get(`${c.index}:${c.candidate}`).valid).length;
 if(job!==18412)unresolvedValid+=uv;
 if(raw){
  const load=(rel,lines=false)=>{const b=fs.readFileSync(path.join(root,rel));assert.equal(hash(b),l.source_hashes[rel]);
   assert.ok(!/(?:sk-[A-Za-z0-9_.-]{12,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,})/.test(b.toString()),'credential-shaped raw input');
   return lines?b.toString().trim().split('\n').map(JSON.parse):JSON.parse(b);};
  const checked=new Set();
  for(const block of [...new Set(p.rows.map(r=>r.block))]){
   const ee=load(`generation-${block}/events.jsonl`,true),warm=new Map(ee.filter(e=>e.event==='warm_start').map(e=>[e.run,e.code_sha256]));
   for(const e of ee.filter(e=>e.event==='admitted'&&e.role==='improve')){
    const r=p.rows.find(r=>r.block===block&&r.request_key===e.key);assert.ok(r);assert.equal(r.index,e.run);
    const deadline=load(`episode-${e.run}/deadline.json`),start=Date.parse(deadline.started_utc)/1000;
    // JS Date precision is milliseconds, Python input timestamps include microseconds.
    assert.ok(Math.abs((p.run_seconds-e.time+start)-r.remaining_seconds)<.0011);
    assert.equal(r.new_parent,e.parent!==warm.get(e.run));assert.equal(r.parent_score,e.snapshot.archive[r.task][e.parent].metric);
    assert.equal(r.generated,ee.some(x=>x.event==='parent_used'&&x.key===e.key));checked.add(`${block}:${e.key}`);
   }
  }
  assert.equal(checked.size,count);
 }
 all.push(...p.rows.map(r=>({job,...r})));
 cohorts.push({job,sha256:pin,admitted:count,unresolved_returns:p.unresolved_returns.length,unresolved_valid_returns:uv,
   new_parent:summarize(p.rows.filter(r=>r.new_parent)),raw_admission_timing_checked:raw});
}
const rr=all.filter(r=>r.job!==18412),ss=rr.filter(r=>r.new_parent);
const out={passed:true,raw_admission_timing_checked:raw,cohorts,
 scheduling:{all_admitted:rr.length,new_parent:summarize(ss),unresolved_valid_returns:unresolvedValid,
 by_remaining:bands.map(b=>({band:b,...summarize(ss.filter(r=>r.remaining_band===b))})),
 by_task:[...new Set(rr.map(r=>r.task))].map(task=>({task,warm:summarize(rr.filter(r=>r.task===task&&!r.new_parent)),new_parent:summarize(rr.filter(r=>r.task===task&&r.new_parent))}))},
 limits:['Observed families, not independent treatment replications or adaptive/no-feedback causal contrast.',
 'Warm/new parent quality, remaining time and survival differ. 300s is a bin edge, not a validated optimal admission threshold.',
 'Outcome counts are LINKED observations. Unresolved valid returns may add successes; do not label all unmatched families as failures.',
 'Raw-event mode independently reconstructs all admission denominators and remaining time, NOT raw code/ancestry linkage.']};
console.log(JSON.stringify(out,null,2));
const destination=process.argv.slice(2).find(x=>x!=='--raw-events');if(destination)fs.writeFileSync(destination,JSON.stringify(out,null,2)+'\n',{flag:'wx'});
