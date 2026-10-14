// Discrete event implementation, independent from Python's free-slot replay.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-4,`${a} != ${b}`);
function permutations(xs){return xs.length?xs.flatMap((v,i)=>permutations(xs.filter((_,j)=>j!==i)).map(t=>[v,...t])):[[]];}
function eventSim(jobs,mapping=null,extra=0){
  let arrivals=jobs.map((j,i)=>({...j,i})).sort((a,b)=>a.arrival-b.arrival || a.session-b.session || a.i-b.i);
  const active=Array(4).fill(null),waiting=[],done=[];let time=arrivals[0]?.arrival??0;
  while(arrivals.length || waiting.length || active.some(Boolean)){
    for(let k=0;k<4;k++)if(active[k]&&active[k].end<=time){done.push(active[k]);active[k]=null;}
    while(arrivals.length&&arrivals[0].arrival<=time)waiting.push(arrivals.shift());
    // At each timestamp, only arrivals already available and actually idle slots.
    for(let wi=0;wi<waiting.length;){
      const j=waiting[wi];const lane=mapping?mapping[j.session]:active.findIndex(x=>x===null);
      if(lane>=0&&active[lane]===null){
        active[lane]={...j,begin:time,end:time+j.duration+extra};waiting.splice(wi,1);
      }else wi++;
    }
    if(active.some(x=>x&&x.end===time))continue;
    if(arrivals.length||active.some(Boolean))time=Math.min(arrivals[0]?.arrival??Infinity,...active.filter(Boolean).map(x=>x.end));
    else assert.equal(waiting.length,0);
  }
  const waits=done.map(j=>j.begin-j.arrival),flow=done.map(j=>j.end-j.arrival).sort((a,b)=>a-b),n=flow.length;
  const mean=flow.reduce((a,b)=>a+b,0)/n;
  return {requests:n,total_wait_seconds:waits.reduce((a,b)=>a+b,0),
    total_flow_seconds:flow.reduce((a,b)=>a+b,0),median_flow_seconds:n?(flow[Math.floor(n/2)]+flow[Math.floor((n-1)/2)])/2:null,
    sample_sd_flow_seconds:n>1?Math.sqrt(flow.reduce((a,v)=>a+(v-mean)**2,0)/(n-1)):null,
    released_by_search_deadline:done.filter(j=>j.end<=j.deadline).length};
}
function check(a,b){for(const[k,v]of Object.entries(a)) v===null?assert.equal(b[k],null):near(v,b[k]);}
const inputs=[['metric-pooling-input.json','bfb4ce38514ebbae01c179d1db2158767e0f8eb3c655d0cfde7885d67cfe4fd0'],
 ['score-pooling-input.json','48c991429fe02f712d522e0b48c331cebe832c2ca7fb32d6ef19dabf043574a6']];
if(require.main===module){
 const dir=process.argv[2],target=JSON.parse(fs.readFileSync(`${dir}/pooling-sensitivity.json`));
 assert.equal(eventSim([{arrival:0,duration:4,deadline:3,session:0}]).released_by_search_deadline,0);
 const rows=[];let checks=0;
 for(const [name,pin]of inputs){
  const raw=fs.readFileSync(`${dir}/${name}`);assert.equal(sha(raw),pin);const data=JSON.parse(raw),ref=target.cases.find(c=>c.source===name);
  assert.equal(ref.source_sha256,pin);
  for(const p of data.pools){
   const r=ref.pools.find(x=>x.block===p.block);const stats=[];
   for(const perm of permutations([1,3,5,7])){
    const m=Object.fromEntries([0,2,4,6].flatMap((v,i)=>[[v,i],[perm[i],i]]));
    const s=eventSim(p.jobs,m);check(s,r.static_details[stats.length]);stats.push(s);checks++;
   }
   for(const extra of [0,5,15,30]){
    const s=eventSim(p.jobs,null,extra),g=r.global_fifo.find(x=>x.extra_dispatch_seconds===extra);check(s,g);checks++;
    assert.equal(stats.filter(t=>s.total_flow_seconds<t.total_flow_seconds-1e-6&&s.released_by_search_deadline>=t.released_by_search_deadline).length,g.static_pairings_strictly_dominated);
    near(1-s.total_flow_seconds/r.observed.total_flow_seconds,g.flow_reduction_vs_observed);
    near(1-s.total_flow_seconds/Math.min(...stats.map(t=>t.total_flow_seconds)),g.flow_reduction_vs_best_static);
   }
   rows.push({batch:data.assigned,block:p.block,arm:p.arm,known:r.known_requests,cancelled:r.cancelled_unknown_duration,
     observed_on_time:r.observed.released_by_search_deadline,
     overheads:r.global_fifo.map(g=>({seconds:g.extra_dispatch_seconds,on_time:g.released_by_search_deadline,
       response_time_reduction_pct:100*g.flow_reduction_vs_observed,
       response_time_reduction_vs_hindsight_best_pairing_pct:100*g.flow_reduction_vs_best_static,
       static_pairings_dominated:g.static_pairings_strictly_dominated}))});
  }
 }
 const result={passed:true,independent_replay_cases:checks,verifier_sha256:sha(fs.readFileSync(__filename)),
   sensitivity_sha256:sha(fs.readFileSync(`${dir}/pooling-sensitivity.json`)),rows,
   limitation:'Checks structural exports, not raw extraction or actual GPU/new-search performance. All cost values are sensitivity, not measured overhead.'};
 fs.writeFileSync(`${dir}/pooling-independent-verification.json`,JSON.stringify(result,null,2),{flag:'wx'});
 process.stdout.write(JSON.stringify({passed:true,independent_replay_cases:checks,pools:rows.length})+'\n');
}
module.exports={eventSim};
