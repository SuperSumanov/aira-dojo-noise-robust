/* Synthetic tests of the independent reader; no experiment results used. */
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {verifyData,SOURCE,PLAN,READER,ORDER,TASKS}=require('./verify_long_effort_20261013.cjs');
const {median,sd}=require('./verify_feedback_effort_20261012.cjs');
function fixture() {
  const rows=Array.from({length:24},(_,i)=>({index:i,block:Math.floor(i/8),lane:Math.floor(i%8/2),slot:i%8,repeat:0,
    arm:ORDER[Math.floor(i/8)],task:TASKS[i%2],seed:213301+i%8,source_commit:SOURCE,run_seconds:1800,pool_seconds:1960,
    score:i%2?(Math.floor(i/8)===1?.010:.020):.99,initial_score:i%2?.030:.98,
    started:true,complete:true,cleanup:true,candidate_returns:1,valid_returns:1}));
  const efforts=rows.map(r=>({index:r.index,task:r.task,arm:r.arm,role:'improve',effort:r.arm==='fast_code'?'none':r.arm,
    enable_thinking:r.arm!=='fast_code',output_cap:32768,request_cap:1500,success:true,seconds:1,elapsed:2,
    finish_reason:'stop',usage:{completion_tokens:10}}));
  const s={assigned:24,started:24,complete:24,source_commit:SOURCE,plan_sha256:PLAN,readout_sha256:READER,
    independent_pools_per_arm:1,no_automatic_expansion:true,gpu_seconds:42000,gpu_hours:42000/3600,
    quality_gate:true,actual_mode_gate:true,structural_gate:true,predeclared_success_gate_met:true,cpu_pairs_passed:12,
    contrasts:TASKS.flatMap(task=>['fast_code','medium'].map(reference=>({task,reference,
      method_best:task===TASKS[0]?.99:.010,reference_best:task===TASKS[0]?.99:.020,oriented_delta:task===TASKS[0]?0:.010}))),by_arm:{}};
  for(const a of ORDER) {s.by_arm[a]={};for(const t of TASKS){const vs=rows.filter(r=>r.arm===a&&r.task===t).map(r=>r.score);s.by_arm[a][t]={median:median(vs),sample_sd:sd(vs)};}}
  const ids=ORDER.map((_,block)=>({block,valid:true,lanes:['a','b','c','d'],service:['e','f']}));
  const csv=()=>[Object.keys(rows[0]).join(','),...rows.map(r=>Object.values(r).map(v=>v===null?'':typeof v==='boolean'?(v?'True':'False'):String(v)).join(','))].join('\n')+'\n';
  return {s,rows,efforts,ids,check:()=>verifyData(s,rows,efforts,csv(),ids),csv};
}
test('complete synthetic qualification',()=>assert.equal(fixture().check().original_gate,true));
test('missing run is not an invented warm outcome',()=>{
  const f=fixture();Object.assign(f.rows[23],{complete:false,score:null});
  Object.assign(f.s,{complete:23,incomplete:true,predeclared_success_gate_met:false});
  assert.equal(f.check().original_gate,false);f.rows[23].score=f.rows[23].initial_score;assert.throws(f.check);
});
test('reject duplicate seed and CSV drift',()=>{
  const f=fixture();f.rows[23].seed=f.rows[22].seed;assert.throws(f.check);
  const g=fixture();assert.throws(()=>verifyData(g.s,g.rows,g.efforts,g.csv().replace('32768','8192').replace('0.99','0.98'),g.ids));
});
test('reject overspend and mismatched plan identity',()=>{
  const f=fixture();f.s.gpu_seconds=45006;assert.throws(f.check);
  const g=fixture();g.s.plan_sha256='0'.repeat(64);assert.throws(g.check);
});
test('reject wrong actual effort or silent cap change',()=>{
  const f=fixture();f.efforts[8].effort='medium';assert.throws(f.check);
  const g=fixture();g.efforts[0].output_cap=8192;assert.throws(g.check);
});
test('gate needs both references and structure',()=>{
  const f=fixture();f.s.structural_gate=false;f.s.predeclared_success_gate_met=false;assert.equal(f.check().original_gate,false);
  const g=fixture();g.s.contrasts[2].oriented_delta=.020;assert.throws(g.check);
});
test('complete quality loss remains a legitimate negative readout',()=>{
  const f=fixture();
  for(const r of f.rows) if(r.arm==='fast_code'&&r.task===TASKS[1]) r.score=.009;
  Object.assign(f.s.contrasts[2],{reference_best:.009,oriented_delta:-1*(.010-.009)});
  f.s.by_arm.fast_code[TASKS[1]]={median:.009,sample_sd:0};
  f.s.quality_gate=false;f.s.predeclared_success_gate_met=false;
  assert.equal(f.check().quality_gate,false);
});
test('no completed xhigh Improve cannot claim an actual-mode pass',()=>{
  const f=fixture();for(const e of f.efforts) if(e.arm==='xhigh') e.success=false;
  f.s.actual_mode_gate=false;f.s.predeclared_success_gate_met=false;
  assert.equal(f.check().actual_mode_gate,false);
});
test('invalid hardware cannot claim a structural pass',()=>{
  const f=fixture();f.ids[1].service[0]='a';assert.throws(f.check);
});
