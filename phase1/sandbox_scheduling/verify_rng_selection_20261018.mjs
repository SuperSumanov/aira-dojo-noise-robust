// Independent arithmetic, schedule and transfer verification of safe exports.
// Does not run Python's reader or access original labels/candidate sources.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const dir=process.argv[2];
const read=n=>JSON.parse(fs.readFileSync(path.join(dir,n),'utf8'));
const hash=n=>crypto.createHash('sha256').update(fs.readFileSync(path.join(dir,n))).digest('hex');
const ensure=(v,m)=>{if(!v)throw Error(m)};
const near=(x,y)=>ensure(Number.isFinite(x)&&Number.isFinite(y)&&Math.abs(x-y)<=1e-12,'numeric mismatch');
const manifest=read('transfer-sha.json');
for(const [n,h] of Object.entries(manifest))ensure(hash(n)===h,'transfer '+n);
const p=read('plan.json'),s=read('summary.json'),r=read('runs.json'),sealed=read('selection-sealed.json'),cl=read('closed.json');
ensure(hash('plan.json')===s.plan_sha256,'plan');
ensure(hash('selection-sealed.json')===s.selection_seal_sha256,'selection seal');
ensure(r.length===32&&p.schedule.length===32&&new Set(r.map(x=>x.index)).size===32,'full denominator');
ensure(sealed.rows.length===24,'selection denominator');
ensure(JSON.stringify(sealed.choices)===JSON.stringify(s.choices),'sealed decisions');
ensure(JSON.stringify(sealed.rows)===JSON.stringify(r.slice(0,24)),'sealed rows');
const modes=['global','sampler','addressed'];
const selections=[];let gate=s.structure;
for(let t=0;t<2;t++){
  const records=r.filter(x=>x.phase==='selection'&&Math.floor(x.program/2)===t);
  const ok=records.length===12&&records.every(x=>x.qualified);
  ensure(s.choices[t].qualified===ok,'choice completeness');
  let selected={};
  if(ok){
    for(const mode of modes){
      const means=[2*t,2*t+1].map(program=>{
        const q=records.filter(x=>x.program===program&&x.mode===mode);
        ensure(q.length===2&&[...q.map(x=>x.seed)].sort().join(',')==='4101,4102','selection seeds');
        const value=(q[0].score+q[1].score)/2*(t===0?1:-1);
        near(value,s.choices[t].by_mode[mode].oriented_means[String(program)]);
        return {program,value};
      });
      means.sort((a,b)=>b.value-a.value||a.program-b.program);selected[mode]=means[0].program;
      ensure(selected[mode]===s.choices[t].by_mode[mode].program,'choice');
    }
  }
  const audit=r.filter(x=>x.phase==='deployment'&&Math.floor(x.program/2)===t);
  const valid=ok&&audit.length===4&&audit.every(x=>x.qualified);
  ensure(s.effects[t].qualified===valid,'audit completeness');
  if(valid){
    for(let z=0;z<2;z++){
      const deltas=[4103,4104].map(seed=>{
        const a=audit.find(x=>x.seed===seed&&x.program===selected.addressed);
        const b=audit.find(x=>x.seed===seed&&x.program===selected[modes[z]]);
        return (a.score-b.score)*(t===0?1:-1);
      });
      deltas.forEach((d,i)=>near(d,s.effects[t].contrasts[z].oriented_deltas[i]));
      const pass=deltas.every(d=>d>=(t===0?0:.001));
      ensure(pass===s.effects[t].contrasts[z].pass_gate,'threshold');gate=gate&&pass;
    }
  }else gate=false;
  selections.push({task:t,qualified:valid,selected});
}
for(let i=0;i<32;i++)for(const key of ['index','program','task','seed','mode','phase','slot','executed_sha256'])ensure(r[i][key]===p.schedule[i][key],'schedule '+key);
for(let k=0;k<4;k++)ensure(r.filter(x=>x.program===k).every(x=>x.slot===k),'arm-invariant physical assignment');
ensure(s.complete===r.filter(x=>x.complete).length&&s.qualified===r.filter(x=>x.qualified).length,'counts');
ensure(s.structure===(!cl.error&&cl.cleanup_verified&&cl.records.length===32&&r.every(x=>x.qualified)),'structure');
ensure(s.quality_gate===Boolean(gate),'final gate');
ensure(p.gpus===4&&s.gpu_seconds>0&&s.gpu_seconds<=14400,'budget');near(s.gpu_hours,s.gpu_seconds/3600);
console.log(JSON.stringify({independent:true,transfer_files:Object.keys(manifest).length,planned:r.length,
  complete:s.complete,qualified:s.qualified,quality_gate:s.quality_gate,gpu_seconds:s.gpu_seconds,
  selections,boundary:'Recomputes decisions/arithmetic and transfer identity, not a second label rescore or independent task replication.'}));
