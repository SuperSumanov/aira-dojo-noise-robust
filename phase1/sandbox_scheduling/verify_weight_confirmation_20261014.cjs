/* Independent frozen32-row arithmetic and separate-repeat quality check. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {csvParse,csvCellMatches,median,sd}=require('./verify_feedback_effort_20261012.cjs');
const TASKS=['aerial-cactus-identification','denoising-dirty-documents'];
const ORDER=['old_medium','new_medium','new_medium','old_medium'];
const sign=t=>t===TASKS[0]?1:-1;
function contrasts(rows) {
  return [0,1].flatMap(repeat=>TASKS.map(task=>{
    const best=arm=>{
      const g=rows.filter(r=>r.repeat===repeat&&r.arm===arm&&r.task===task);
      assert.equal(g.length,4);assert(g.every(r=>r.complete&&Number.isFinite(r.score)));
      return (sign(task)>0?Math.max:Math.min)(...g.map(r=>r.score));
    };
    const n=best('new_medium'),o=best('old_medium');
    return {repeat,task,method:'new_medium',reference:'old_medium',method_best:n,reference_best:o,oriented_delta:sign(task)*(n-o)};
  }));
}
const quality=cs=>cs.every(c=>c.oriented_delta>=(sign(c.task)>0?-1e-12:.001));
function verifyData(s,rows,calls,csvText,ids,inputs,pins) {
  for(const [k,v] of Object.entries(pins)) assert.equal(s[k],v);
  assert.equal(s.assigned,32);assert.equal(rows.length,32);assert.equal(inputs.length,32);
  assert.equal(s.independent_pools_per_arm,2);assert.equal(s.no_automatic_expansion,true);
  assert(Number.isInteger(s.gpu_seconds)&&s.gpu_seconds>0&&s.gpu_seconds<=54000&&s.gpu_seconds%6===0);
  assert.equal(s.gpu_hours,s.gpu_seconds/3600);
  const csv=csvParse(csvText),header=csv.shift();assert.equal(csv.length,32);
  assert.deepEqual([...header].sort(),Object.keys(rows[0]).sort());
  rows.forEach((r,i)=>{
    assert.equal(r.index,i);assert.equal(r.block,Math.floor(i/8));assert.equal(r.repeat,Math.floor(i/16));
    assert.equal(r.lane,Math.floor(i%8/2));assert.equal(r.slot,i%8);assert.equal(r.task,TASKS[i%2]);
    assert.equal(r.arm,ORDER[r.block]);assert.equal(r.seed,214501+100*r.repeat+i%8);
    assert.equal(r.source_commit,pins.source_commit);assert.equal(r.run_seconds,1800);assert.equal(r.pool_seconds,1960);
    ['complete','cleanup','started'].forEach(k=>assert.equal(typeof r[k],'boolean'));
    ['candidate_returns','valid_returns'].forEach(k=>assert(Number.isInteger(r[k])&&r[k]>=0));
    assert(r.valid_returns<=r.candidate_returns);assert(Number.isFinite(r.initial_score));
    assert.equal(r.initial_score,rows[i%2].initial_score);
    if(r.complete) {assert(r.started&&r.cleanup&&Number.isFinite(r.score));assert(sign(r.task)*(r.score-r.initial_score)>=-1e-12);}
    else assert.equal(r.score,null);
    assert.equal(csv[i].length,header.length);header.forEach((k,j)=>assert(csvCellMatches(r[k],csv[i][j]),`CSV ${i}/${k}`));
    assert.equal(inputs[i].index,i);assert.equal(typeof inputs[i].passed,'boolean');
    assert(/^[a-f0-9]{64}$/.test(inputs[i].expected_sha256));
    if(inputs[i].passed)assert.equal(inputs[i].observed_sha256,inputs[i].expected_sha256);
  });
  // Match complete first inputs within each seed, never across different RNGs.
  for(const r of rows) {
    const pair=rows.filter(x=>x.seed===r.seed);assert.equal(pair.length,2);
    assert.equal(inputs[pair[0].index].expected_sha256,inputs[pair[1].index].expected_sha256);
  }
  assert.equal(s.runtime_input_gate,inputs.every(x=>x.passed));
  assert.equal(s.started,rows.filter(r=>r.started).length);assert.equal(s.complete,rows.filter(r=>r.complete).length);
  for(const c of calls) {
    assert(Number.isInteger(c.index)&&c.index>=0&&c.index<32);const r=rows[c.index];
    assert.equal(c.arm,r.arm);assert.equal(c.task,r.task);assert(['draft','improve','debug','analyze'].includes(c.role));
    assert.equal(c.effort,'medium');assert.equal(c.enable_thinking,true);
    assert.equal(c.model_id,c.arm==='old_medium'?'qwen3.8-27b':'qwen3.8-27b-score-step30');
    assert.equal(c.output_cap,c.role==='analyze'?8192:32768);assert.equal(c.request_cap,c.role==='analyze'?600:1500);
    assert.equal(typeof c.success,'boolean');assert(Number.isFinite(c.seconds)&&c.seconds>=0);
    assert(Number.isFinite(c.elapsed)&&c.elapsed>=0);
  }
  let cs=null,passed=null;
  if(s.complete<32) {assert.equal(s.incomplete,true);assert.equal(s.predeclared_success_gate_met,false);}
  else {
    cs=contrasts(rows);passed=quality(cs);assert.deepEqual(s.contrasts,cs);assert.equal(s.quality_gate,passed);
    const actual=ORDER.every((_,b)=>calls.some(c=>Math.floor(c.index/8)===b&&c.role==='improve'&&c.success));
    assert.equal(s.actual_mode_gate,actual);assert.equal(typeof s.structural_gate,'boolean');
    assert.equal(s.predeclared_success_gate_met,passed&&actual&&s.structural_gate&&s.runtime_input_gate);
    assert.equal(ids.length,4);if(s.structural_gate) {
      assert.equal(s.cpu_pairs_passed,16);
      ids.forEach((d,b)=>{assert.equal(d.block,b);assert(d.valid);assert.equal(d.lanes.length,4);assert.equal(d.service.length,2);
        assert.equal(new Set([...d.lanes,...d.service]).size,6);assert.deepEqual(d.lanes,ids[0].lanes);
        assert.deepEqual([...d.service].sort(),[...ids[0].service].sort());});
    }
    assert.equal(s.by_pool.length,8);
    for(const p of s.by_pool) {
      const v=rows.filter(r=>r.block===p.block&&r.task===p.task).map(r=>r.score);
      assert.equal(p.n,4);assert.equal(p.repeat,Math.floor(p.block/2));assert.equal(p.arm,ORDER[p.block]);
      assert.equal(p.best,(sign(p.task)>0?Math.max:Math.min)(...v));
      assert(Math.abs(p.median-median(v))<1e-12);assert(Math.abs(p.sample_sd-sd(v))<1e-12);
    }
  }
  return {status:'passed',assigned:32,complete:s.complete,contrasts:cs,quality_gate:passed,
    runtime_input_gate:s.runtime_input_gate,original_gate:s.predeclared_success_gate_met,
    gpu_seconds:s.gpu_seconds,...pins,limitation:'Two paired pool repeats share one service/allocation. Not32 independent replicates, test generalization or training-cost ROI.'};
}
function selftest() {
  const rows=Array.from({length:32},(_,i)=>({repeat:Math.floor(i/16),arm:ORDER[Math.floor(i/8)],task:TASKS[i%2],complete:true,
    score:i%2===0?.9:ORDER[Math.floor(i/8)]==='new_medium'?.018:.02}));
  assert(quality(contrasts(rows)));
  const bad=structuredClone(rows);bad.filter(r=>r.repeat===1&&r.arm==='new_medium'&&r.task===TASKS[1]).forEach(r=>r.score=.021);
  assert(!quality(contrasts(bad)));
  const loss=structuredClone(rows);loss.filter(r=>r.repeat===1&&r.arm==='new_medium'&&r.task===TASKS[0]).forEach(r=>r.score=.89);
  assert(!quality(contrasts(loss)));
  const incomplete=structuredClone(rows);incomplete[0].complete=false;assert.throws(()=>contrasts(incomplete));
  const missing=rows.slice(1);assert.throws(()=>contrasts(missing));
  const pins={source_commit:'a'.repeat(40),plan_sha256:'b'.repeat(64),readout_sha256:'c'.repeat(64)};
  const rich=rows.map((r,i)=>({...r,index:i,block:Math.floor(i/8),lane:Math.floor(i%8/2),slot:i%8,
    seed:214501+100*r.repeat+i%8,source_commit:pins.source_commit,run_seconds:1800,pool_seconds:1960,
    cleanup:true,started:true,candidate_returns:1,valid_returns:1,initial_score:i%2===0?.8:.05}));
  const calls=rich.map(r=>({index:r.index,arm:r.arm,task:r.task,role:'improve',effort:'medium',enable_thinking:true,
    model_id:r.arm==='old_medium'?'qwen3.8-27b':'qwen3.8-27b-score-step30',output_cap:32768,request_cap:1500,success:true,seconds:5,elapsed:10}));
  const inputs=rich.map(r=>({index:r.index,passed:true,expected_sha256:'d'.repeat(64),observed_sha256:'d'.repeat(64)}));
  const ids=ORDER.map((_,block)=>({block,valid:true,lanes:['g0','g1','g2','g3'],service:['g4','g5']}));
  const s={...pins,assigned:32,started:32,complete:32,independent_pools_per_arm:2,no_automatic_expansion:true,
    gpu_seconds:48000,gpu_hours:48000/3600,runtime_input_gate:true,contrasts:contrasts(rich),quality_gate:true,
    actual_mode_gate:true,structural_gate:true,predeclared_success_gate_met:true,cpu_pairs_passed:16,
    by_pool:ORDER.flatMap((arm,block)=>TASKS.map(task=>{
      const v=rich.filter(r=>r.block===block&&r.task===task).map(r=>r.score);
      return {block,repeat:Math.floor(block/2),arm,task,n:4,best:(sign(task)>0?Math.max:Math.min)(...v),median:median(v),sample_sd:sd(v)};
    }))};
  const h=Object.keys(rich[0]);const csv=[h.join(','),...rich.map(r=>h.map(k=>typeof r[k]==='boolean'?r[k]?'True':'False':r[k]).join(','))].join('\n');
  assert.equal(verifyData(s,rich,calls,csv,ids,inputs,pins).original_gate,true);
  assert.throws(()=>verifyData({...s,quality_gate:false},rich,calls,csv,ids,inputs,pins));
  const badInput=structuredClone(inputs);badInput[1].passed=false;
  assert.throws(()=>verifyData(s,rich,calls,csv,ids,badInput,pins));
  assert.throws(()=>verifyData(s,rich,calls,csv.replace('214501','214599'),ids,inputs,pins));
  return {selftests:9,passed:true};
}
if(require.main===module) {
  if(process.argv[2]==='--test')console.log(JSON.stringify(selftest()));
  else {
    const root=process.argv[2],pins=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
    ['source_commit','plan_sha256','readout_sha256'].forEach(k=>assert(pins[k]));
    const read=n=>JSON.parse(fs.readFileSync(path.join(root,n),'utf8')),s=read('summary.json');
    const result=verifyData(s,read('runs.json'),read('effort.json'),fs.readFileSync(path.join(root,'runs.csv'),'utf8'),
      s.complete===32?read('identity.json'):null,read('input-checks.json'),pins);
    const names=['summary.json','runs.json','effort.json','runs.csv','input-checks.json'];if(s.complete===32)names.push('identity.json');
    result.transfer_sha256=Object.fromEntries(names.map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,n))).digest('hex')]));
    fs.writeFileSync(path.join(root,'independent-verification.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
    console.log(JSON.stringify(result));
  }
}
module.exports={verifyData,contrasts,quality,selftest};
