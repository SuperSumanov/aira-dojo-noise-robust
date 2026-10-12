/* Independent arithmetic/CSV verification. Never imports the Python reader. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const ORDER = ['medium','fast_code','feedback_think','feedback_think','fast_code','medium'];
const TASKS = ['aerial-cactus-identification','denoising-dirty-documents'];
function csvParse(text) {
  const records=[]; let row=[],cell='',quoted=false;
  for(let i=0;i<text.length;i++) {
    const c=text[i];
    if(c==='"') {if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}
    else if(c===','&&!quoted){row.push(cell);cell='';}
    else if(c==='\n'&&!quoted){row.push(cell.replace(/\r$/,''));records.push(row);row=[];cell='';}
    else cell+=c;
  }
  assert.equal(quoted,false);
  if(cell||row.length){row.push(cell);records.push(row);}
  return records;
}
const thinking=(arm,role)=>role==='analyze'||arm==='medium'||(arm==='feedback_think'&&role==='debug');
const median=vs=>{vs=[...vs].sort((a,b)=>a-b);const n=vs.length;return n%2?vs[(n-1)/2]:(vs[n/2-1]+vs[n/2])/2;};
const sd=vs=>{const m=vs.reduce((a,b)=>a+b)/vs.length;return Math.sqrt(vs.reduce((a,b)=>a+(b-m)**2,0)/(vs.length-1));};
function contrast(rows) {
  const scores=new Map();
  for(let b=0;b<6;b++) for(const task of TASKS) {
    const rr=rows.filter(r=>r.block===b&&r.task===task);
    assert.equal(rr.length,4);
    scores.set(`${b}/${task}`,rr.every(r=>r.complete)?(task===TASKS[0]?Math.max(...rr.map(r=>r.score)):Math.min(...rr.map(r=>r.score))):null);
  }
  const result=[];
  for(let rep=0;rep<2;rep++) for(const task of TASKS) for(const ref of ORDER.slice(0,2)) {
    const blocks=ORDER.map((a,b)=>({a,b})).filter(x=>Math.floor(x.b/3)===rep);
    const m=scores.get(`${blocks.find(x=>x.a==='feedback_think').b}/${task}`);
    const r=scores.get(`${blocks.find(x=>x.a===ref).b}/${task}`);
    result.push({repeat:rep,task,reference:ref,method_best:m,reference_best:r,oriented_delta:m===null||r===null?null:(task===TASKS[0]?1:-1)*(m-r)});
  }
  return result;
}
function verify(root,expectedSource='3f119700a84d5975acef8bcff9949e188c60aefc',expectedPlan='a85d6332621414e7a5fae031bb419e769769b5724ec6cf574677bf211176462a') {
  assert(/^[a-f0-9]{40}$/.test(expectedSource));assert(/^[a-f0-9]{64}$/.test(expectedPlan));
  const read=n=>JSON.parse(fs.readFileSync(path.join(root,n),'utf8'));
  const hash=n=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,n))).digest('hex');
  const s=read('summary.json'),rows=read('runs.json'),efforts=read('effort.json');
  const csv=csvParse(fs.readFileSync(path.join(root,'runs.csv'),'utf8')),header=csv.shift();
  assert.equal(rows.length,48);assert.equal(csv.length,48);assert.equal(s.assigned,48);
  const encode=v=>v===null?'':typeof v==='boolean'?(v?'True':'False'):String(v);
  rows.forEach((r,i)=>{
    assert.equal(r.index,i);assert.equal(r.block,Math.floor(i/8));assert.equal(r.lane,Math.floor(i%8/2));
    assert.equal(r.repeat,Math.floor(r.block/3));assert.equal(r.task,TASKS[i%2]);assert.equal(r.arm,ORDER[r.block]);
    assert.equal(r.seed,213101+100*r.repeat+2*r.lane+i%2);assert.equal(r.run_seconds,1020);assert.equal(r.pool_seconds,1180);
    assert.equal(r.source_commit,expectedSource);
    assert.equal(csv[i].length,header.length);header.forEach((k,j)=>assert.equal(csv[i][j],encode(r[k]),`csv${i}/${k}`));
    if(r.complete){assert(r.started&&r.cleanup&&Number.isFinite(r.score));assert(r.score>=0&&r.score<=1);}
    else assert.equal(r.score,null);
  });
  assert.equal(s.source_commit,rows[0].source_commit);
  assert.equal(s.plan_sha256,expectedPlan);
  assert.equal(s.complete,rows.filter(r=>r.complete).length);
  assert(s.gpu_seconds>0&&s.gpu_seconds<=46800);assert.equal(s.gpu_seconds%6,0);assert.equal(s.gpu_hours,s.gpu_seconds/3600);
  if(s.prior_failure_gpu_seconds!==undefined){assert.equal(s.prior_failure_gpu_seconds,1968);assert.equal(s.window_gpu_seconds,1968+s.gpu_seconds);assert(s.window_gpu_seconds<=46800);assert.equal(s.window_gpu_hours,s.window_gpu_seconds/3600);}
  for(const e of efforts){assert.equal(e.arm,rows[e.index].arm);assert.equal(e.task,rows[e.index].task);assert(['draft','improve','debug','analyze'].includes(e.role));assert.equal(e.enable_thinking,thinking(e.arm,e.role));assert.equal(e.effort,e.enable_thinking?'medium':'none');assert(e.seconds>=0);}
  const all=rows.every(r=>r.complete);let contrasts=null,quality=null,mechanism=null,stats=null;
  const files=['summary.json','runs.json','runs.csv','effort.json'];
  if(!all){assert.equal(s.incomplete,true);assert.equal(s.started,rows.filter(r=>r.started).length);assert.equal(s.predeclared_success_gate_met,false);}
  else {
    contrasts=contrast(rows);assert.deepEqual(contrasts,s.contrasts);
    quality=contrasts.every(x=>x.oriented_delta>=(x.task===TASKS[0]?-1e-12:.001));assert.equal(quality,s.quality_gate);
    mechanism=[2,3].every(b=>efforts.some(e=>Math.floor(e.index/8)===b&&e.role==='improve'&&!e.enable_thinking&&e.success)&&efforts.some(e=>Math.floor(e.index/8)===b&&e.role==='debug'&&e.enable_thinking&&e.success));
    assert.equal(mechanism,s.mechanism_gate);assert.equal(s.predeclared_success_gate_met,quality&&mechanism&&s.structural_gate);
    assert.equal(s.cpu_pairs_passed,24);
    const ids=read('identity.json');files.push('identity.json');assert.equal(ids.length,6);
    ids.forEach(i=>{assert(i.valid);assert.deepEqual(i.lanes,ids[0].lanes);assert.deepEqual([...i.service].sort(),[...ids[0].service].sort());assert.equal(new Set([...i.lanes,...i.service]).size,6);});
    stats={};for(const arm of ORDER.slice(0,3)){stats[arm]={};for(const task of TASKS){const vs=rows.filter(r=>r.arm===arm&&r.task===task).map(r=>r.score);assert.equal(vs.length,8);const v={median:median(vs),sample_sd:sd(vs)};for(const k of Object.keys(v))assert(Math.abs(v[k]-s.by_arm[arm][task][k])<1e-12);stats[arm][task]=v;}}
  }
  return {status:'passed',method:'Independent Node arithmetic and CSV parsing; not an independent rerun of every remote integrity check.',
    assigned:rows.length,started:rows.filter(r=>r.started).length,complete:s.complete,csv_json_cell_parity:true,
    complete_matrix:all,quality_gate:quality,mechanism_gate:mechanism,original_gate:s.predeclared_success_gate_met,
    source_commit:s.source_commit,plan_sha256:s.plan_sha256,gpu_seconds:s.gpu_seconds,gpu_hours:s.gpu_hours,
    contrasts,by_arm:stats,transfer_sha256:Object.fromEntries(files.map(n=>[n,hash(n)])),
    limitation:'Two pool repeats and two already-used development tasks; within-pool searches are dependent. Known CoT-retry-like strategy qualification, not novelty confirmation.'};
}
if(require.main===module){const root=process.argv[2];const out=verify(root,process.argv[3],process.argv[4]);fs.writeFileSync(path.join(root,'independent-verification.json'),JSON.stringify(out,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(out));}
module.exports={verify,contrast,csvParse,thinking,median,sd};
