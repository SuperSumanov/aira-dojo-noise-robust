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
const selections=[],auditHeadroom=[];let gate=s.structure;
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
    const sign=t===0?1:-1;
    auditHeadroom.push({task:t,by_seed:[4103,4104].map(seed=>{
      const q=audit.filter(x=>x.seed===seed);
      const best=Math.max(...q.map(x=>sign*x.score));
      return {seed,oriented_program_difference:sign*(q.find(x=>x.program===2*t+1).score-q.find(x=>x.program===2*t).score),
        observed_library_regret:Object.fromEntries(modes.map(m=>[m,best-sign*q.find(x=>x.program===selected[m]).score]))};
    })});
    for(let z=0;z<2;z++){
      const deltas=[4103,4104].map(seed=>{
        const a=audit.find(x=>x.seed===seed&&x.program===selected.addressed);
        const b=audit.find(x=>x.seed===seed&&x.program===selected[modes[z]]);
        return (a.score-b.score)*(t===0?1:-1);
      });
      deltas.forEach((d,i)=>near(d,s.effects[t].contrasts[z].oriented_deltas[i]));
      near((deltas[0]+deltas[1])/2,s.effects[t].contrasts[z].median);
      near(Math.abs(deltas[0]-deltas[1])/Math.sqrt(2),s.effects[t].contrasts[z].sample_sd);
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
const accounting=read('accounting.json');
ensure(accounting.job==='19249'&&accounting.allocation_gpu_seconds===s.gpu_seconds,'actual allocation cost');
ensure(accounting.conservative_gpu_seconds+856<=5*3600,'window cap including aborted batch');
console.log(JSON.stringify({independent:true,transfer_files:Object.keys(manifest).length,planned:r.length,
  complete:s.complete,qualified:s.qualified,quality_gate:s.quality_gate,gpu_seconds:s.gpu_seconds,
  selections,boundary:'Recomputes decisions/arithmetic and transfer identity, not a second label rescore or independent task replication.'}));
console.log(JSON.stringify({descriptive_observed_library_headroom:auditHeadroom,
  boundary:'Oracle over these two already-executed programs only, not an achievable seed-blind policy or an upper bound on new candidate generation.'}));
// Defined before any pilot score inspection (HK10/18 01:29).
// This is a secondary proxy-alignment diagnostic; NEVER changes the gate.
const retained=[];
for(let t=0;t<2;t++){
  const sign=t===0?1:-1;
  const arms={};
  for(const mode of modes){
    const q=r.filter(x=>x.phase==='selection'&&Math.floor(x.program/2)===t&&x.mode===mode);
    const valid=q.length===4&&q.every(x=>x.qualified);
    const best=rr=>rr.slice().sort((a,b)=>sign*(b.score-a.score)||a.index-b.index)[0];
    arms[mode]={qualified:valid,executions:q.length,best:valid?best(q).score:null,
      by_seed:valid?[4101,4102].map(seed=>({seed,best:best(q.filter(x=>x.seed===seed)).score})):null};
  }
  const complete=modes.every(m=>arms[m].qualified);
  retained.push({task:t,arms,contrasts:complete?modes.slice(0,2).map(reference=>({reference,
    oriented_deltas_by_seed:arms.addressed.by_seed.map((x,i)=>({seed:x.seed,delta:sign*(x.best-arms[reference].by_seed[i].best)})),
    oriented_all4_best_delta:sign*(arms.addressed.best-arms[reference].best)})):null});
}
console.log(JSON.stringify({secondary_retained_artifact_diagnostic:retained,
  boundary:'Equal4 selection executions/task/arm, already-used DEV, no independent held-out quality. Best-of-realized-artifacts differs from expected retrained-program quality. Descriptive only, not a replacement gate or full agent search.'}));
