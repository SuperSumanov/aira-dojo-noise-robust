// Independent JS recomputation from allowlisted event export + prior readouts.
const fs=require('fs'), path=require('path'), assert=require('assert/strict'), crypto=require('crypto');
const input=process.argv[2], output=process.argv[3];
const raw=fs.readFileSync(input), d=JSON.parse(raw);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const close=(a,b)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-11,`${a} != ${b}`);
const best=(xs,s)=>xs.reduce((a,b)=>s*b>s*a?b:a);
const median=xs=>{const a=[...xs].sort((a,b)=>a-b);return (a[1]+a[2])/2};
assert.deepEqual(d.cuts,[600,1020,1500,1800]);assert.equal(d.quality_or_speedup_claim,false);
let endpoints=0,pools=0;const descriptive=[];
for(const source of d.sources){
  const prior=path.join(__dirname,source.name==='score'?'weight_confirmation_18269_closed':'metric_deployment_18412_closed');
  assert.equal(sha(fs.readFileSync(path.join(prior,'summary.json'))),source.summary_sha256);
  const original=JSON.parse(fs.readFileSync(path.join(prior,'runs.json')));
  assert.equal(source.rows.length,original.length);
  for(const r of source.rows){
    const old=original.find(o=>o.index===r.index);assert.ok(old.complete);
    assert.equal(r.returned,old.candidate_returns);assert.equal(r.valid_events.length,old.valid_returns);
    assert.equal(r.task,old.task);assert.equal(r.arm,old.arm);
    for(let i=0;i<d.cuts.length;i++){
      const value=best([r.initial,...r.valid_events.filter(e=>e.elapsed<=d.cuts[i]).map(e=>e.score)],r.sign);
      close(value,r.curve[i].score);
    }
    close(r.curve[3].score,old.score);endpoints++;
  }
  for(const p of source.pools){
    const rows=source.rows.filter(r=>r.block===p.block&&r.task===p.task);assert.equal(rows.length,4);
    for(let i=0;i<d.cuts.length;i++){
      const values=rows.map(r=>r.curve[i].score),mean=values.reduce((a,b)=>a+b,0)/4;
      close(best(values,p.sign),p.prefix_curves[i].best);close(median(values),p.prefix_curves[i].median);
      close(Math.sqrt(values.reduce((s,v)=>s+(v-mean)**2,0)/3),p.prefix_curves[i].sample_sd);
    }
    const events=rows.flatMap(r=>r.valid_events.map(e=>({...e,at:e.elapsed+r.offset,index:r.index}))).sort((a,b)=>a.at-b.at||a.index-b.index);
    let incumbent=p.initial;const records=[];
    for(const e of events)if(p.sign*(e.score-incumbent)>1e-12){records.push({at:e.at,gain:p.sign*(e.score-incumbent),score:e.score});incumbent=e.score;}
    assert.equal(records.length,p.pool_records);assert.deepEqual(records,p.records);
    assert.equal(events.length,p.valid_returns);
    assert.equal(events.filter(e=>p.sign*(e.score-p.initial)>1e-12).length,p.above_initial);
    assert.equal(records.length?records.at(-1).at:null,p.last_record_at);
    assert.equal(records.find(e=>p.sign*(e.score-p.initial)>=.001)?.at??null,p.first_material_gain_at);
    close(p.sign*(p.prefix_curves[3].best-p.prefix_curves[1].best),p.post_1020_gain);pools++;
  }
  descriptive.push({source:source.name,assigned:source.assigned,
    denoising:source.pools.filter(p=>p.sign===-1).map(p=>({block:p.block,arm:p.arm,valid:p.valid_returns,records:p.pool_records,
      best_at_1020:p.prefix_curves[1].best,best_at_1800:p.prefix_curves[3].best,post_1020_gain:p.post_1020_gain,
      first_material_gain_at:p.first_material_gain_at,last_record_at:p.last_record_at}))});
}
assert.equal(endpoints,80);assert.equal(pools,20);
const result={passed:true,verified_endpoints:endpoints,verified_task_pool_cells:pools,input_sha256:sha(raw),
  independent_recompute:'80 prior endpoints, all prefix curves/medians/sample SD, actual-wall-order record gains',
  boundary:'Source extraction and original external score recomputation are not rerun by JS. This is descriptive, not intervention or gain confirmation.',descriptive};
fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(result));
