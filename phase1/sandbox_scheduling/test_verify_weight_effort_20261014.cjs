const assert=require('node:assert/strict'),{test}=require('node:test');
const {verifyData,ORDER,TASKS}=require('./verify_weight_effort_20261014.cjs');
function fixture(){
  const pins={source_commit:'a'.repeat(40),plan_sha256:'b'.repeat(64),readout_sha256:'c'.repeat(64)};
  const rows=Array.from({length:32},(_,i)=>({index:i,block:Math.floor(i/8),lane:Math.floor(i%8/2),slot:i%8,repeat:0,
    arm:ORDER[Math.floor(i/8)],task:TASKS[i%2],seed:214401+i%8,source_commit:pins.source_commit,
    run_seconds:1800,pool_seconds:1960,score:i%2?(ORDER[Math.floor(i/8)].startsWith('new_')?.01:.02):.99,
    initial_score:i%2?.03:.98,started:true,complete:true,cleanup:true,candidate_returns:1,valid_returns:1}));
  const calls=rows.map(r=>({index:r.index,arm:r.arm,task:r.task,role:'improve',effort:r.arm.endsWith('fast')?'none':'medium',
    enable_thinking:r.arm.endsWith('medium'),model_id:r.arm.startsWith('new_')?'qwen3.8-27b-score-step30':'qwen3.8-27b',
    output_cap:32768,request_cap:1500,success:true,seconds:1,elapsed:2,finish_reason:'stop',usage:{completion_tokens:1}}));
  const s={...pins,assigned:32,started:32,complete:32,independent_pools_per_arm:1,no_automatic_expansion:true,
    gpu_seconds:50004,gpu_hours:50004/3600,quality_gate:true,actual_mode_gate:true,structural_gate:true,
    predeclared_success_gate_met:true,cpu_pairs_passed:16,
    contrasts:['medium','fast'].flatMap(mode=>TASKS.map(task=>({task,mode,primary:mode==='medium',reference:'old_'+mode,method:'new_'+mode,
      method_best:task===TASKS[0]?.99:.01,reference_best:task===TASKS[0]?.99:.02,oriented_delta:task===TASKS[0]?0:.01}))),
    by_arm:Object.fromEntries(ORDER.map(a=>[a,Object.fromEntries(TASKS.map(t=>[t,{median:t===TASKS[0]?.99:a.startsWith('new_')?.01:.02,sample_sd:0}]))]))};
  const ids=ORDER.map((_,block)=>({block,valid:true,lanes:['a','b','c','d'],service:['e','f']}));
  const csv=()=>[Object.keys(rows[0]).join(','),...rows.map(r=>Object.values(r).map(v=>v===null?'':typeof v==='boolean'?(v?'True':'False'):String(v)).join(','))].join('\n')+'\n';
  return {s,rows,calls,ids,pins,csv,check:()=>verifyData(s,rows,calls,csv(),ids,pins)};
}
test('complete factorial',()=>assert.equal(fixture().check().original_gate,true));
test('incomplete remains32 and not filled from initial',()=>{const f=fixture();Object.assign(f.rows[31],{complete:false,score:null});Object.assign(f.s,{complete:31,incomplete:true,predeclared_success_gate_met:false});assert.equal(f.check().original_gate,false);f.rows[31].score=.03;assert.throws(f.check);});
test('wrong adapter route rejected',()=>{const f=fixture();f.calls[8].model_id='qwen3.8-27b';assert.throws(f.check);});
test('wrong effort rejected',()=>{const f=fixture();f.calls[0].effort='medium';assert.throws(f.check);});
test('overspend rejected',()=>{const f=fixture();f.s.gpu_seconds=54006;assert.throws(f.check);});
test('nonprimary fast gain cannot repair medium loss',()=>{const f=fixture();for(const r of f.rows)if(r.arm==='new_medium'&&r.task===TASKS[1])r.score=.025;Object.assign(f.s.contrasts[1],{method_best:.025,oriented_delta:-1*(.025-.02)});f.s.by_arm.new_medium[TASKS[1]].median=.025;f.s.quality_gate=false;f.s.predeclared_success_gate_met=false;assert.equal(f.check().quality_gate,false);});
test('CSV corruption rejected',()=>{const f=fixture();assert.throws(()=>verifyData(f.s,f.rows,f.calls,f.csv().replace('0.99','0.9'),f.ids,f.pins));});
test('hardware reuse mismatch rejected',()=>{const f=fixture();f.ids[3].lanes[0]='other';assert.throws(f.check);});
