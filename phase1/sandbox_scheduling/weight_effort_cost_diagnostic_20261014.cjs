// Closed-batch diagnosis only. No extrapolated speedup or replacement quality gate.
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto'), assert=require('node:assert/strict');
const pins={
  'runs.json':'f739e7ea279d185dae236d2c5afc27343514b8973326804d3074648ffa9cd7da',
  'effort.json':'f8458001c06ee57ec4f95860615752abbcb3dd6496e71250a5c7bc9e126eebb4'
};
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
function median(values){
  assert(values.length>0 && values.every(Number.isFinite));
  const a=[...values].sort((x,y)=>x-y), n=a.length;
  return n%2?a[(n-1)/2]:(a[n/2-1]+a[n/2])/2;
}
function sampleSD(a){assert(a.length>1);const mean=a.reduce((x,y)=>x+y,0)/a.length;return Math.sqrt(a.reduce((x,y)=>x+(y-mean)**2,0)/(a.length-1));}
function analyze(runs,calls){
  assert.equal(runs.length,32);assert(runs.every(r=>r.complete));
  const arms=['old_fast','old_medium','new_fast','new_medium'];
  const tasks=['aerial-cactus-identification','denoising-dirty-documents'];
  const rows=[];
  for(const arm of arms) for(const task of tasks){
    const r=runs.filter(x=>x.arm===arm&&x.task===task);assert.equal(r.length,4);
    const code=calls.filter(x=>x.arm===arm&&x.task===task&&x.role!=='analyze');
    const returned=code.filter(x=>x.success);
    assert(returned.every(x=>x.seconds>0&&Number.isFinite(x.usage.completion_tokens)));
    const first=r.map(x=>code.find(c=>c.index===x.index));
    assert(first.every(x=>x&&x.success&&x.role==='improve'));
    const sign=task===tasks[0]?1:-1;
    const improvement=r.map(x=>sign*(x.score-x.initial_score));
    assert(improvement.every(x=>x>=0));
    rows.push({arm,task,assigned:4,improved_runs:improvement.filter(x=>x>0).length,
      endpoint_median:median(r.map(x=>x.score)),endpoint_sample_sd:sampleSD(r.map(x=>x.score)),
      improvement_over_common_warm_median:median(improvement),
      code_calls:code.length,returned_code_calls:returned.length,failed_or_deadline_code_calls:code.length-returned.length,
      length_limited_returns:returned.filter(x=>x.finish_reason==='length').length,
      returned_candidates:r.reduce((a,x)=>a+x.candidate_returns,0),
      valid_candidates:r.reduce((a,x)=>a+x.valid_returns,0),
      returned_call_seconds_median:median(returned.map(x=>x.seconds)),
      returned_call_completion_tokens_median:median(returned.map(x=>x.usage.completion_tokens)),
      first_call_seconds_median:median(first.map(x=>x.seconds)),
      returned_call_output_tokens_per_end_to_end_second_median:median(returned.map(x=>x.usage.completion_tokens/x.seconds))
    });
  }
  return {schema:1,source_pins:pins,assigned:32,rows,
    interpretation:{
      new_primary_positive_result:false,original_quality_gate:false,actual_input_gate:false,
      history_control:'All endpoints are measured against the same supplied warm start; no previous pool winner is substituted.',
      independent_pools_per_cell:1,
      time_measurement:'Returned-call wall latency includes queue/prefill/decoding. Not GPU decode throughput; failures/deadline calls are counted separately, not assigned token rates.',
      mechanism:'Adapter-mode latency may limit opportunities, but rank128 LoRA overhead, load and request differences are not causally separated. Do not infer hardware speedup or simulate free extra searches.',
      limitation:'Post-hoc diagnosis of development data, with actual-prompt mismatch. Within-pool runs are correlated. Higher count of runs improving a weak initial program is not a higher final pool score or a model-learning effect.'
    }};
}
if(require.main===module){
  assert.equal(median([3,1,2,4]),2.5);assert.equal(median([3,1,2]),2);assert.equal(sampleSD([1,2,3]),1);
  const [root,output]=process.argv.slice(2);assert(root&&output);
  const read=n=>{const b=fs.readFileSync(path.join(root,n));assert.equal(sha(b),pins[n]);return JSON.parse(b)};
  const result=analyze(read('runs.json'),read('effort.json'));
  fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({assigned:result.assigned,groups:result.rows.length,output_sha256:sha(fs.readFileSync(output)),original_quality_gate:false,actual_input_gate:false,new_quality_evidence:false}));
}
module.exports={analyze,median,sampleSD};
