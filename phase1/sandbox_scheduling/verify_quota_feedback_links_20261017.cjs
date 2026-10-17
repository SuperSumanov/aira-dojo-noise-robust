// Independent aggregation, phase consistency, published-best and full-denominator checks.
// The original journal/event association is not independently re-extracted here.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
function load(name,pin){const b=fs.readFileSync(path.join(__dirname,name));if(pin)assert.equal(hash(b),pin);return JSON.parse(b);}
const phase=load('quota-feedback-link-20261017.safe.json','cddfd609f92720f3547528ed420973f2931fef06273bab064ec0afa3cc1f30b9');
const upstream=load('quota-upstream-link-20261017.safe.json','29a763e7e7cebcf770de3aea481559c5b699f2aa0d4a3e4aeb2ba847ab1656a3');
const lineage=load('colocation_18807_closed/adaptation-lineage-extension-20261017.safe.json',phase.lineage_sha256);
const slack=load('colocation_18807_closed/quota-slack-20261017-v1.safe.json','d9c4bfb490baf1a6924262ee72939c07d163e6eb79ba2b0173d6fef710de5181');
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-7);
assert.equal(hash(fs.readFileSync(path.join(__dirname,'closed_quota_feedback_link_20261017.py'))),phase.reader_sha256);
assert.equal(hash(fs.readFileSync(path.join(__dirname,'closed_quota_upstream_link_20261017.py'))),upstream.reader_sha256);
const allPhase=[],allGen=[],allPublished=[],categories=new Map(),deadlineTails=[];
for(let block=0;block<4;block++){
 const p=phase.pools[block],u=upstream.pools[block];assert.equal(p.block,block);assert.equal(u.block,block);
 const initial=new Map(lineage.groups.filter(g=>g.block===block).map(g=>[g.task,g.initial]));
 const published=p.rows.filter(r=>r.native_valid).sort((a,b)=>a.publication_time-b.publication_time);
 assert.equal(published.length,p.published_valid);
 for(const r of published){
  assert.ok(r.linked && r.external_valid);
  const sign=r.task==='denoising-dirty-documents'?-1:1;
  const gain=sign*(r.score-initial.get(r.task));
  close(gain,r.gain_vs_prior_matched_published_best);
  assert.equal(r.new_published_best,gain>1e-12);
  if(gain>1e-12)initial.set(r.task,r.score);
 }
 assert.equal(p.new_best_publications,published.filter(r=>r.new_published_best).length);
 const rmap=new Map(u.published.map(r=>[r.key,r]));assert.equal(rmap.size,u.published.length);
 for(const role of ['improve','debug','analyze']){
  // Compare like-for-like: raw waiting versus raw segment integrals, not the
  // former horizon=0 statistic which clips each request at its run deadline.
  let raw=0,clipped=0;
  for(const segment of slack.pools[block].segments)for(const r of segment.blocked)if(r.role===role){
   raw+=segment.seconds;clipped+=Math.max(0,Math.min(segment.seconds,r.slack_at_start));
  }
  close(p.borrowable_request_seconds_by_role[role],raw);
  close(clipped,slack.pools[block].by_slack[0].request_seconds_by_role[role]);
  if(raw-clipped>1e-9)deadlineTails.push({block,role,raw_minus_predeadline_seconds:raw-clipped});
 }
 for(const r of u.published){
  const a=p.rows.filter(a=>a.index===r.index && a.candidate===r.candidate);assert.equal(a.length,1);
  assert.equal(r.new_published_best,!!a[0].new_published_best);
  assert.equal(r.native_valid,a[0].native_valid);assert.equal(r.valid,a[0].external_valid);
  assert.equal(r.journal_role_supported,true);
 }
 for(const role of ['improve','debug'])close(u.generations.filter(r=>r.role===role).reduce((s,r)=>s+r.observed_borrowable_wait_seconds,0),p.borrowable_request_seconds_by_role[role]);
 for(const g of u.generations){
  const r=rmap.get(g.key);assert.equal(g.linked_publication,!!r);
  if(r){assert.equal(r.index,g.index);assert.equal(r.role,g.role);close(r.observed_borrowable_wait_seconds,g.observed_borrowable_wait_seconds);}
  const kind=!r?'no_linked_publication':!r.native_valid?'published_invalid':r.new_published_best?'published_new_best':'published_valid_other';
  const key=g.role+':'+kind;
  const v=categories.get(key)||{role:g.role,category:kind,requests:0,exposed_requests:0,observed_borrowable_request_seconds:0};
  v.requests++;v.exposed_requests+=g.observed_borrowable_wait_seconds>0;v.observed_borrowable_request_seconds+=g.observed_borrowable_wait_seconds;categories.set(key,v);
 }
 allPhase.push(...p.rows);allGen.push(...u.generations);allPublished.push(...u.published);
}
assert.equal(allPhase.length,78);assert.equal(allGen.length,107);assert.equal(allPublished.length,74);
assert.equal(allPhase.filter(r=>r.native_valid).length,37);
assert.equal(allPublished.filter(r=>r.role==='debug'&&r.valid).length,10);
const blockedBestAnalyze=allPhase.filter(r=>r.new_published_best&&r.observed_borrowable_wait_seconds>0);
const blockedBestDebug=allPublished.filter(r=>r.role==='debug'&&r.new_published_best&&r.observed_borrowable_wait_seconds>0);
assert.equal(blockedBestAnalyze.length,2);assert.equal(blockedBestDebug.length,1);
const result={passed:true,verifier_sha256:hash(fs.readFileSync(__filename)),analyze_requests:78,generation_requests:107,
 linked_generation_publications:74,debug_valid:10,debug_new_best:3,
 blocked_best_analyze_wait_seconds:blockedBestAnalyze.map(r=>r.observed_borrowable_wait_seconds),
 blocked_best_debug_wait_seconds:blockedBestDebug.map(r=>r.observed_borrowable_wait_seconds),
 generation_wait_by_observed_publication:[...categories.values()],deadline_tail_accounting:deadlineTails,
 verifier_correction:'Initial comparison incorrectly equated raw waiting with prior deadline-clipped horizon0; strict raw-segment integration fixes the estimand mismatch, without changing input data, tolerance or any experiment gate.',
 limits:['Independent arithmetic, exact receipt/source SHA and phase cross-check; not an independent raw journal/event extraction.',
 'Observed outcomes after waiting are post-treatment/censored; do not call unknown/invalid requests inherently worthless or infer saved time.',
 'No real pooled-quota result, no original endpoint or gate change.']};
fs.writeFileSync(path.join(__dirname,'quota-feedback-links-independent-20261017.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result));
