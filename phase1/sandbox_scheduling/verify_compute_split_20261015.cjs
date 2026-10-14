// Independent safe-export verification; no remote data or Python implementation.
const fs = require('fs');
const assert = require('assert/strict');
const crypto = require('crypto');
const hash = x => crypto.createHash('sha256').update(x).digest('hex');
const near = (a,b) => assert.ok(Math.abs(a-b)<1e-4, `${a} != ${b}`);
function replay(jobs, capacity, end) {
  const slots = Array(capacity).fill(-Infinity), waits=[], ends=[];
  for (const j of [...jobs].sort((a,b)=>a.arrival-b.arrival || a.original_start-b.original_start)) {
    let k=0;
    for(let i=1;i<slots.length;i++) if(slots[i]<slots[k]) k=i;
    const begin = Math.max(j.arrival, slots[k]);
    assert.ok(j.duration>=0); slots[k]=begin+j.duration;
    waits.push(begin-j.arrival); ends.push(slots[k]);
  }
  waits.sort((a,b)=>a-b);
  const n=waits.length;
  return {jobs:n,capacity,total_wait_seconds:waits.reduce((a,b)=>a+b,0),
    wait_median:n?(waits[Math.floor(n/2)]+waits[Math.floor((n-1)/2)])/2:null,
    finishes_by_pool_end:ends.filter(t=>t<=end).length,
    last_finish_past_end:Math.max(0,...ends.map(t=>t-end))};
}
function area(s) {
  // Build unique intervals and independently seek last state at each left edge.
  const {start,end,streams}=s;
  const times=[...new Set([start,end,...streams.flatMap(x=>x.map(r=>Math.max(start,Math.min(end,r[0]))))])].sort((a,b)=>a-b);
  const total={generation_queued_seconds:0,generation_held_seconds:0,
    execution_queued_seconds:0,execution_held_seconds:0,
    generation_full_seconds:0,execution_full_seconds:0,
    queue_despite_idle_exec_seconds:0,queued_request_seconds_with_idle_exec:0,
    exec_busy_seconds_when_idle_slot:0};
  for(let i=0;i<times.length-1;i++) {
    const t=times[i],dt=times[i+1]-t;
    const v=streams.map(stream=>stream.filter(r=>Math.max(start,Math.min(end,r[0]))<=t).at(-1)||[t,0,0]);
    const q=v.slice(1).reduce((a,r)=>a+r[1],0), active=v.slice(1).reduce((a,r)=>a+r[2],0);
    total.generation_queued_seconds+=dt*v[0][1];total.generation_held_seconds+=dt*v[0][2];
    total.execution_queued_seconds+=dt*q;total.execution_held_seconds+=dt*active;
    total.generation_full_seconds+=dt*(v[0][2]===4);total.execution_full_seconds+=dt*(active===4);
    total.queue_despite_idle_exec_seconds+=dt*(q>0 && active<4);
    total.queued_request_seconds_with_idle_exec+=dt*q*(active<4);
    total.exec_busy_seconds_when_idle_slot+=dt*active*(active<4);
  }
  return total;
}
function run(file, expected) {
  const bytes=fs.readFileSync(file);assert.equal(hash(bytes),expected);
  const d=JSON.parse(bytes);assert.equal(d.quality_claim,false);
  assert.equal(d.safe_structural_streams.length,d.pools.length);
  const rows=d.pools.map((p,i)=>{
    const s=d.safe_structural_streams[i];assert.equal(s.block,p.block);
    near(s.end-s.start,p.duration_seconds);
    const independent=area(s);
    for(const k of Object.keys(p.host_areas)) if(k in independent) near(independent[k],p.host_areas[k]);
    for(const r of p.fixed_arrival_replay) {
      const rr=replay(s.execution_jobs,r.capacity,s.end);
      for(const [k,val] of Object.entries(rr)) val===null?assert.equal(r[k],null):near(r[k],val);
    }
    near(s.execution_jobs.reduce((a,j)=>a+j.duration,0),p.host_areas.execution_held_seconds);
    const originalWait=s.execution_jobs.reduce((a,j)=>a+j.original_start-j.arrival,0);
    // Original area also includes cancelled requests; do not force equality.
    assert.ok(originalWait<=p.host_areas.execution_queued_seconds+1e-4);
    return {block:p.block,arm:p.arm,assigned:8,execution_requests:s.execution_jobs.length,
      execution_busy_slot_fraction:p.exec_held_fraction,exec_sample_util_pct:p.pooled_gpu_sample_utilization_pct,
      original_completed_request_wait_seconds:originalWait,
      cancelled_request_wait_seconds:p.host_areas.execution_queued_seconds-originalWait,
      queue_despite_idle_exec_seconds:independent.queue_despite_idle_exec_seconds,
      queued_request_seconds_with_idle_exec:independent.queued_request_seconds_with_idle_exec,
      pooled_four_wait_seconds:p.fixed_arrival_replay[1].total_wait_seconds,
      two_slot_replay_completed:p.fixed_arrival_replay[0].finishes_by_pool_end,
      two_slot_replay_overrun_seconds:p.fixed_arrival_replay[0].last_finish_past_end,
      sampled_peak_memory_mib:Math.max(...p.lane_telemetry.map(t=>t.peak_memory_mib)),
      telemetry_min_coverage:Math.min(...p.lane_telemetry.map(t=>t.window_coverage))};
  });
  return {input_sha256:expected,passed:true,assigned:d.assigned,rows,
    limitation:'Independently verifies the safe-export integrals/replay, not raw event extraction or raw telemetry. Post-hoc fixed arrivals; CPU interference, feedback and cancelled workload omitted from replay. No achieved speedup or quality claim.'};
}
if(require.main===module){
  assert.deepEqual(replay([{arrival:0,original_start:0,duration:4},{arrival:0,original_start:4,duration:4}],1,5),{jobs:2,capacity:1,total_wait_seconds:4,wait_median:2,finishes_by_pool_end:1,last_finish_past_end:3});
  const result={verifier_sha256:hash(fs.readFileSync(__filename)),cases:[
    run(process.argv[2],'456f12bc37f07bf0f1af81840ef0b0319cc07bc8fccea0a110b6b37ded1a0c61'),
    run(process.argv[3],'a1a50d97472aab9a03d211eeabe08151989008ed4d4d8bcffdc5e80be6bd8739')]};
  fs.writeFileSync(process.argv[4],JSON.stringify(result,null,2),{flag:'wx'});
  process.stdout.write(JSON.stringify(result,null,2)+'\n');
}
module.exports={replay,area};
