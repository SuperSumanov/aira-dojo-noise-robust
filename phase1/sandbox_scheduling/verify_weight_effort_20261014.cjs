/* Independent32-row arithmetic/identity reader, not experimental qualification. */
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {csvParse,csvCellMatches,median,sd}=require('./verify_feedback_effort_20261012.cjs');
const ORDER=['old_fast','new_medium','new_fast','old_medium'];
const TASKS=['aerial-cactus-identification','denoising-dirty-documents'];
const sign=t=>t===TASKS[0]?1:-1;
function verifyData(s,rows,calls,csvText,ids,pins) {
  for(const [key,pin] of Object.entries(pins)) assert.equal(s[key],pin);
  assert.equal(s.assigned,32);assert.equal(rows.length,32);
  assert.equal(s.independent_pools_per_arm,1);assert.equal(s.no_automatic_expansion,true);
  assert(Number.isInteger(s.gpu_seconds)&&s.gpu_seconds>0&&s.gpu_seconds<=54000&&s.gpu_seconds%6===0);
  assert.equal(s.gpu_hours,s.gpu_seconds/3600);
  const csv=csvParse(csvText), header=csv.shift();
  assert.equal(csv.length,32);assert.equal(new Set(header).size,header.length);
  assert.deepEqual([...header].sort(),Object.keys(rows[0]).sort());
  rows.forEach((r,i)=>{
    assert.equal(r.index,i);assert.equal(r.block,Math.floor(i/8));
    assert.equal(r.lane,Math.floor(i%8/2));assert.equal(r.slot,i%8);assert.equal(r.repeat,0);
    assert.equal(r.arm,ORDER[r.block]);assert.equal(r.task,TASKS[i%2]);assert.equal(r.seed,214401+i%8);
    assert.equal(r.source_commit,pins.source_commit);assert.equal(r.run_seconds,1800);assert.equal(r.pool_seconds,1960);
    for(const k of ['started','complete','cleanup']) assert.equal(typeof r[k],'boolean');
    for(const k of ['candidate_returns','valid_returns']) assert(Number.isInteger(r[k])&&r[k]>=0);
    assert(r.valid_returns<=r.candidate_returns);assert(Number.isFinite(r.initial_score));
    assert.equal(r.initial_score,rows[i%2].initial_score);
    if(r.complete) {
      assert(r.started&&r.cleanup&&Number.isFinite(r.score));
      assert(sign(r.task)*(r.score-r.initial_score)>=-1e-12);
    } else assert.equal(r.score,null);
    assert.equal(csv[i].length,header.length);
    header.forEach((k,j)=>assert(csvCellMatches(r[k],csv[i][j]),`CSV ${i}/${k}`));
  });
  assert.equal(s.started,rows.filter(r=>r.started).length);assert.equal(s.complete,rows.filter(r=>r.complete).length);
  for(const c of calls) {
    assert(Number.isInteger(c.index)&&c.index>=0&&c.index<32);
    assert.equal(c.arm,rows[c.index].arm);assert.equal(c.task,rows[c.index].task);
    assert(['draft','improve','debug','analyze'].includes(c.role));
    const effort=c.role==='analyze'||c.arm.endsWith('_medium')?'medium':'none';
    assert.equal(c.effort,effort);assert.equal(c.enable_thinking,effort!=='none');
    assert.equal(c.model_id,c.arm.startsWith('new_')?'qwen3.8-27b-score-step30':'qwen3.8-27b');
    assert.equal(c.output_cap,c.role==='analyze'?8192:32768);assert.equal(c.request_cap,c.role==='analyze'?600:1500);
    assert.equal(typeof c.success,'boolean');assert(Number.isFinite(c.seconds)&&c.seconds>=0);
    assert(Number.isFinite(c.elapsed)&&c.elapsed>=0);
    assert([null,'stop','length','tool_calls','content_filter'].includes(c.finish_reason));
    assert(Object.values(c.usage).every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0));
  }
  let contrasts=null, quality=null, actual=null;
  if(s.complete<32) {
    assert.equal(s.incomplete,true);assert.equal(s.predeclared_success_gate_met,false);
  } else {
    const best=(a,t)=>{
      const group=rows.filter(r=>r.arm===a&&r.task===t);assert.equal(group.length,4);
      return (sign(t)>0?Math.max:Math.min)(...group.map(r=>r.score));
    };
    contrasts=['medium','fast'].flatMap(mode=>TASKS.map(task=>({task,mode,primary:mode==='medium',reference:'old_'+mode,method:'new_'+mode,
      method_best:best('new_'+mode,task),reference_best:best('old_'+mode,task),
      oriented_delta:sign(task)*(best('new_'+mode,task)-best('old_'+mode,task))})));
    assert.deepEqual(s.contrasts,contrasts);
    quality=contrasts.filter(c=>c.primary).every(c=>c.oriented_delta>=(sign(c.task)>0?-1e-12:.001));
    actual=ORDER.every(a=>calls.some(c=>c.arm===a&&c.role==='improve'&&c.success));
    assert.equal(s.quality_gate,quality);assert.equal(s.actual_mode_gate,actual);
    assert.equal(typeof s.structural_gate,'boolean');
    assert.equal(s.predeclared_success_gate_met,quality&&actual&&s.structural_gate);
    assert.equal(ids.length,4);
    if(s.structural_gate) {
      assert.equal(s.cpu_pairs_passed,16);
      ids.forEach((d,i)=>{
        assert.equal(d.block,i);assert(d.valid);assert.equal(d.lanes.length,4);assert.equal(d.service.length,2);
        assert.equal(new Set([...d.lanes,...d.service]).size,6);
        assert.deepEqual(d.lanes,ids[0].lanes);assert.deepEqual([...d.service].sort(),[...ids[0].service].sort());
      });
    }
    for(const a of ORDER) for(const t of TASKS) {
      const values=rows.filter(r=>r.arm===a&&r.task===t).map(r=>r.score);
      assert(Math.abs(s.by_arm[a][t].median-median(values))<=1e-12);
      assert(Math.abs(s.by_arm[a][t].sample_sd-sd(values))<=1e-12);
    }
  }
  return {status:'passed',assigned:32,complete:s.complete,quality_gate:quality,actual_mode_gate:actual,
    original_gate:s.predeclared_success_gate_met,contrasts,gpu_seconds:s.gpu_seconds,...pins,
    limitation:'One pool per condition. Arithmetic/CSV/metadata verification does not replace remote scoring and runtime receipts or establish daily training causality.'};
}
function verify(root,pins) {
  const read=n=>JSON.parse(fs.readFileSync(path.join(root,n),'utf8'));
  const s=read('summary.json'),names=['summary.json','runs.json','runs.csv','effort.json'];
  if(s.complete===32) names.push('identity.json');
  const out=verifyData(s,read('runs.json'),read('effort.json'),fs.readFileSync(path.join(root,'runs.csv'),'utf8'),s.complete===32?read('identity.json'):null,pins);
  out.transfer_sha256=Object.fromEntries(names.map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,n))).digest('hex')]));
  return out;
}
if(require.main===module) {
  const root=process.argv[2],pins=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
  for(const key of ['source_commit','plan_sha256','readout_sha256']) assert(pins[key]);
  const result=verify(root,pins);
  fs.writeFileSync(path.join(root,'independent-verification.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify(result));
}
module.exports={verifyData,verify,ORDER,TASKS};
