/* Independent arithmetic for the approved exploratory24, not a new experiment. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {csvParse,csvCellMatches,median,sd} = require('./verify_feedback_effort_20261012.cjs');
const SOURCE = '49dec91477e7d6dc8cfc1f7e86780a69205d499d';
const PLAN = 'cef33dddaf5973d067b8b7c1b415a1f1512e73b6fae5cdb23deb6a3ed410bd00';
const READER = '09b873a4496b8239191f2adc03df65f34db6faa7000efb387c6b6c917538b77c';
const ORDER = ['medium','xhigh','fast_code'];
const TASKS = ['aerial-cactus-identification','denoising-dirty-documents'];
const sign = task=>task===TASKS[0]?1:-1;
function verifyData(s, rows, efforts, csvText, identities) {
  assert.equal(s.source_commit,SOURCE); assert.equal(s.plan_sha256,PLAN);
  assert.equal(s.readout_sha256,READER);
  assert.equal(s.assigned,24); assert.equal(rows.length,24);
  assert.equal(s.independent_pools_per_arm,1); assert.equal(s.no_automatic_expansion,true);
  assert(Number.isInteger(s.gpu_seconds)&&s.gpu_seconds>0&&s.gpu_seconds<=45000);
  assert.equal(s.gpu_seconds%6,0); assert.equal(s.gpu_hours,s.gpu_seconds/3600);
  const csv=csvParse(csvText), header=csv.shift();
  assert.equal(csv.length,24); assert.equal(new Set(header).size,header.length);
  assert.deepEqual([...header].sort(),Object.keys(rows[0]).sort());
  rows.forEach((r,i)=>{
    assert.equal(r.index,i); assert.equal(r.block,Math.floor(i/8));
    assert.equal(r.lane,Math.floor(i%8/2)); assert.equal(r.slot,i%8);
    assert.equal(r.repeat,0); assert.equal(r.seed,213301+i%8);
    assert.equal(r.arm,ORDER[r.block]); assert.equal(r.task,TASKS[i%2]);
    assert.equal(r.source_commit,SOURCE); assert.equal(r.run_seconds,1800); assert.equal(r.pool_seconds,1960);
    for(const k of ['started','complete','cleanup']) assert.equal(typeof r[k],'boolean');
    for(const k of ['candidate_returns','valid_returns']) assert(Number.isInteger(r[k])&&r[k]>=0);
    assert(r.valid_returns<=r.candidate_returns);
    assert(Number.isFinite(r.initial_score)&&r.initial_score>=0);
    assert.equal(r.initial_score,rows[i%2].initial_score);
    if(r.complete) {
      assert(r.started&&r.cleanup&&Number.isFinite(r.score)&&r.score>=0);
      assert(sign(r.task)*(r.score-r.initial_score)>=-1e-12);
      if(r.task===TASKS[0]) assert(r.score<=1);
    } else assert.equal(r.score,null);
    assert.equal(csv[i].length,header.length);
    header.forEach((k,j)=>assert(csvCellMatches(r[k],csv[i][j]),`CSV row${i}/${k}`));
  });
  assert.equal(s.started,rows.filter(r=>r.started).length);
  assert.equal(s.complete,rows.filter(r=>r.complete).length);
  for(const e of efforts) {
    assert(Number.isInteger(e.index)&&e.index>=0&&e.index<24);
    assert.equal(e.arm,rows[e.index].arm); assert.equal(e.task,rows[e.index].task);
    assert(['draft','improve','debug','analyze'].includes(e.role));
    const effort=e.role==='analyze'?'medium':e.arm==='fast_code'?'none':e.arm;
    assert.equal(e.effort,effort); assert.equal(e.enable_thinking,effort!=='none');
    assert.equal(e.output_cap,e.role==='analyze'?8192:32768);
    assert.equal(e.request_cap,e.role==='analyze'?600:1500);
    assert.equal(typeof e.success,'boolean');
    assert(Number.isFinite(e.seconds)&&e.seconds>=0);
    assert(Number.isFinite(e.elapsed)&&e.elapsed>=0);
    assert([null,'stop','length','tool_calls','content_filter'].includes(e.finish_reason));
    assert(e.usage&&typeof e.usage==='object'&&!Array.isArray(e.usage));
    assert(Object.values(e.usage).every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0));
  }
  let contrasts=null, quality=null, actual=null;
  if(s.complete!==24) {
    assert.equal(s.incomplete,true); assert.equal(s.predeclared_success_gate_met,false);
  } else {
    const best=(arm,task)=>{
      const rr=rows.filter(r=>r.arm===arm&&r.task===task); assert.equal(rr.length,4);
      return (task===TASKS[0]?Math.max:Math.min)(...rr.map(r=>r.score));
    };
    contrasts=TASKS.flatMap(task=>['fast_code','medium'].map(reference=>{
      const method_best=best('xhigh',task),reference_best=best(reference,task);
      return {task,reference,method_best,reference_best,oriented_delta:sign(task)*(method_best-reference_best)};
    }));
    assert.deepEqual(contrasts,s.contrasts);
    quality=contrasts.every(r=>r.oriented_delta>=(r.task===TASKS[0]?-1e-12:.001));
    actual=ORDER.every(a=>efforts.some(e=>e.arm===a&&e.role==='improve'&&e.success));
    assert.equal(s.quality_gate,quality); assert.equal(s.actual_mode_gate,actual);
    assert.equal(typeof s.structural_gate,'boolean');
    assert.equal(s.predeclared_success_gate_met,quality&&actual&&s.structural_gate);
    assert(Number.isInteger(s.cpu_pairs_passed)&&s.cpu_pairs_passed>=0&&s.cpu_pairs_passed<=12);
    assert.equal(identities.length,3);
    const deviceValid=identities.every((r,b)=>r.block===b&&r.valid&&r.lanes.length===4&&r.service.length===2&&
      new Set([...r.lanes,...r.service]).size===6&&JSON.stringify(r.lanes)===JSON.stringify(identities[0].lanes)&&
      JSON.stringify([...r.service].sort())===JSON.stringify([...identities[0].service].sort()));
    if(s.structural_gate) {assert(deviceValid); assert.equal(s.cpu_pairs_passed,12);}
    for(const arm of ORDER) for(const task of TASKS) {
      const vs=rows.filter(r=>r.arm===arm&&r.task===task).map(r=>r.score);
      for(const [k,v] of Object.entries({median:median(vs),sample_sd:sd(vs)}))
        assert(Math.abs(s.by_arm[arm][task][k]-v)<=1e-12);
    }
  }
  return {status:'passed',assigned:24,complete:s.complete,quality_gate:quality,actual_mode_gate:actual,
    original_gate:s.predeclared_success_gate_met,gpu_seconds:s.gpu_seconds,contrasts,
    source_commit:SOURCE,plan_sha256:PLAN,
    scope:'Independent matrix, CSV and arithmetic only; remote scoring, timing and CPU isolation are separate receipts.',
    limitation:'One pool per arm, shared archive, fixed order and prefix cache. Not independent replication or novelty evidence.'};
}
function verify(root) {
  const read=n=>JSON.parse(fs.readFileSync(path.join(root,n),'utf8'));
  const s=read('summary.json'),files=['summary.json','runs.json','runs.csv','effort.json'];
  if(s.complete===24) files.push('identity.json');
  const v=verifyData(s,read('runs.json'),read('effort.json'),fs.readFileSync(path.join(root,'runs.csv'),'utf8'),
    s.complete===24?read('identity.json'):null);
  v.transfer_sha256=Object.fromEntries(files.map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,n))).digest('hex')]));
  return v;
}
if(require.main===module) {
  const v=verify(process.argv[2]);
  fs.writeFileSync(path.join(process.argv[2],'independent-verification.json'),JSON.stringify(v,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify(v));
}
module.exports={verify,verifyData,SOURCE,PLAN,READER,ORDER,TASKS};
