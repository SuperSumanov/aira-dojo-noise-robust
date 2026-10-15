// Fixed-observed-history sensitivity: remove ALL execution queue waits.
// Not a four-GPU scheduler simulation, a new prompt policy, or a quality bound
// over unobserved future candidates. No live trial or protected outcome reads.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const read=p=>JSON.parse(fs.readFileSync(p));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const gainFile=process.argv[2],out=process.argv[3],gain=read(gainFile),all=[];
const sources=[];
function removed(intervals,at){return intervals.reduce((s,[a,b])=>s+Math.max(0,Math.min(b,at)-a),0)}
assert.equal(removed([[10,20],[40,60]],50),20);
assert.equal(removed([[10,20]],5),0);
assert.equal(removed([[10,20]],20),10);
for(const src of gain.sources){
  const timingFile=path.join(__dirname,'compute_split_20261015_cpu',src.name+'-pooling-input.json');
  const timing=read(timingFile);assert.equal(timing.plan_sha256,src.plan_sha256);
  sources.push({name:src.name,timing_sha256:hash(timingFile),plan_sha256:src.plan_sha256});
  const shifted=[];
  for(const r of src.rows){
    const pool=timing.pools.find(p=>p.block===r.block);assert.ok(pool);
    const requests=pool.jobs.filter(j=>j.session===r.index%8),cancelled=pool.cancelled.filter(j=>j.session===r.index%8);
    const intervals=[...requests.map(j=>[j.arrival,j.original_start]),...cancelled.map(j=>[j.arrival,j.cancelled_at])].sort((a,b)=>a[0]-b[0]);
    for(let i=0;i<intervals.length;i++){
      assert.ok(intervals[i][1]>=intervals[i][0]);
      if(i)assert.ok(intervals[i][0]>=intervals[i-1][1]);
    }
    for(const e of r.valid_events){
      const at=e.elapsed+r.offset,w=removed(intervals,at);
      assert.ok(w<=e.elapsed+1e-5);
      shifted.push({index:r.index,block:r.block,task:r.task,arm:r.arm,score:e.score,observed:e.elapsed,no_exec_wait:e.elapsed-w,removed_wait:w});
    }
  }
  for(const p of src.pools){
    const events=shifted.filter(e=>e.block===p.block&&e.task===p.task);
    const best=(xs)=>[p.initial,...xs.map(e=>e.score)].reduce((a,b)=>p.sign*b>p.sign*a?b:a);
    const observed=best(events.filter(e=>e.observed<=1020));
    assert.ok(Math.abs(observed-p.prefix_curves[1].best)<1e-12);
    const shiftedBest=best(events.filter(e=>e.no_exec_wait<=1020));
    const improved=p.sign*(shiftedBest-observed)>1e-12;
    all.push({source:src.name,block:p.block,task:p.task,arm:p.arm,observed_at_1020:observed,
      fixed_history_without_exec_wait_at_1020:shiftedBest,oriented_change:p.sign*(shiftedBest-observed),
      changed:improved,newly_on_time_known_valid:events.filter(e=>e.observed>1020&&e.no_exec_wait<=1020).length,
      shifted_known_events:events});
  }
}
const result={kind:'fixed_history_no_execution_wait_quality_sensitivity',gain_source_sha256:hash(gainFile),sources,
  tested_threshold_seconds:1020,task_pool_cells:all.length,rows:all,
  new_gpu_jobs:0,new_model_calls:0,quality_claim:false,
  limitations:['All observed generation, execution, scoring and nonqueue gaps fixed. Only admitted/cancelled execution waiting removed.',
  'Uses already observed closed development scores. Not a deployable decision rule and never uses live outcomes.',
  'Zero-wait scenario ignores finite hardware and prompt/history/load changes; not an attainable shared-FIFO forecast.',
  'Cannot bound gains from unobserved tail candidates or changed search trajectories. Late/unknown cancelled scores never invented.',
  '1020s prefixes were generated with1800s prompts; neither this nor unchanged cells negate the new real17-minute experiment.',
  'No frozen primary gate, planned matrix, or budget is changed.']};
fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({task_pool_cells:all.length,denoising:all.filter(r=>r.task==='denoising-dirty-documents').map(({shifted_known_events,...r})=>r)}));
