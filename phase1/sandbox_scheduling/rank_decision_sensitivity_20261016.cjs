// Secondary interpretation of sealed replays, not a policy or new success gate.
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
function analyze(rows){
 assert.equal(rows.length,16);assert.ok(rows.every(r=>r.complete&&r.valid&&Number.isFinite(r.score)));
 const out=[];
 for(let task=0;task<2;task++){
  const sign=task===0?1:-1,p=[2*task,2*task+1],pairs=[];
  for(let rep=0;rep<2;rep++){
   const b=rep===0?[0,1]:[3,2];
   const modes=b.map(block=>p.map(program=>{
    const r=rows.filter(x=>x.program===program&&x.block===block);assert.equal(r.length,1);return r[0];}));
   const [solo,co]=modes,oriented=r=>sign*r.score;
   const best=rs=>oriented(rs[0])>oriented(rs[1])?0:oriented(rs[1])>oriented(rs[0])?1:null;
   const soloChoice=best(solo),coChoice=best(co);
   pairs.push({repeat:rep,solo_winner_program:soloChoice===null?null:p[soloChoice],
    colocated_winner_program:coChoice===null?null:p[coChoice],
    retrospective_regret_if_solo_is_deployment:coChoice===null?null:Math.max(...solo.map(oriented))-oriented(solo[coChoice]),
    selected_programs_are_source_fixed:true,
    effects:p.map((program,i)=>({program,step_loss_fraction:(solo[i].steps-co[i].steps)/solo[i].steps,
     oriented_score_change:oriented(co[i])-oriented(solo[i]),
     less_work_and_better_observed_score:co[i].steps<solo[i].steps&&oriented(co[i])>oriented(solo[i])}))});
  }
  out.push({task_index:task,task:rows.find(r=>r.program===p[0]).task,pairs});
 }
 return out;
}
const fixture=Array.from({length:16},(_,i)=>({program:i%4,block:Math.floor(i/4),complete:true,valid:true,
 score:(i%2?2:1)*([1,2].includes(Math.floor(i/4))?-1:1),steps:100,task:'synthetic'}));
assert.equal(analyze(fixture)[1].pairs[0].retrospective_regret_if_solo_is_deployment,1);
assert.throws(()=>analyze(fixture.slice(1)));
if(process.argv[2]){
 const bytes=fs.readFileSync(process.argv[2]),rows=JSON.parse(bytes);
 const result={input_runs_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
  posthoc:true,tasks:analyze(rows),
  boundaries:[
   'Regret is retrospective and assumes exclusive execution is the deployment target; that target is not established by this experiment.',
   'Colocated winner is correct for the observed colocated outputs. Lower scores are not automatically mislabeled or an unfair evaluation.',
   'Equal program caps and identical source/input are not equal paired-block cost: solo runs sequentially and co runs simultaneously.',
   'These source-fixed replay differences neither predict a new adaptive search trajectory nor show net gains after re-evaluation costs.',
   'Less work with a better score does not identify early stopping or regularization as its cause; no branch trace or randomized work intervention was recorded.'
  ]};
 if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify(result));
}else console.log(JSON.stringify({self_tests:true}));
