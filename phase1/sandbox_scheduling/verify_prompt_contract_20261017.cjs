// Independent aggregation of role-separated input diagnostics; not a second raw extraction.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const specs=[
 [18770,'pooling_18770_closed',45,'509f8138a081cccdc6d6701bee7c63c02961017b9bc6f1cbc2b3fb34a7549472','f743ad365376fd4f7271488b89fb732f60b2f515aa88a0402a9b19c43ff89985'],
 [18807,'colocation_18807_closed',52,'f09e8eb34caf2081034b9f14ff7ac479e76e44360131ec89cfd56b9409143659','7e2f0a32846c33a749527baf607b8ddb72a57e164a9797eee24ff7c847ab6f33'],
 [18997,'selective_18997_closed',51,'dbc4ff11b419fd7735f378be4c3e3e16be1bff5c47bc3fcb62c854c1c354a982','e84ae1aff509ba92e205769a7a7e75219a759371fcaf050920d1a7b5ebbc4e4b'],
 [18412,'metric_deployment_18412_closed',99,'5b411aa9e39a1b46cb83614ddfbde564d2a6dfd49d076fd5227a598eec36bbbb','227df27281df7c5d725cb84cfd9f3ba513932e6b68ca6f5e1d36220ac6ee1398']
];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const result=[];
for(const [job,dir,n,h1,h2]of specs){
 const [v1,v2]=['prompt-contract-20261017.safe.json','prompt-contract-v2-20261017.safe.json'].map((file,i)=>{
  const b=fs.readFileSync(path.join(__dirname,dir,file));assert.equal(hash(b),[h1,h2][i]);return JSON.parse(b);
 });
 assert.equal(v2.v1_receipt_sha256,h1);assert.equal(v2.job,job);assert.equal(v2.rows.length,n);
 assert.deepEqual(v1.source_hashes,v2.source_hashes);assert.equal(v1.lineage_sha256,v2.lineage_sha256);
 assert.equal(new Set(v2.rows.map(r=>`${r.index}:${r.candidate}`)).size,n);
 for(const r of v2.rows){
  assert.equal(r.status,'recorded');assert.equal(r.full_parent_in_all_improve_prompts,true);
  assert.equal(r.full_parent_in_any_improve_prompt,true);assert.equal(r.prompt_characters.length,r.prompt_count);
  assert.ok(r.prompt_characters.every(x=>x>r.parent_characters));assert.ok(r.explicit_five_fold.every(x=>x===true));
 }
 for(const k of ['eligible_returned_improve','full_parent_all','full_parent_any','forced_five_fold'])assert.equal(v2.summary[k],n);
 result.push({job,returned_improve:n,complete_parent:n,forced_five_fold:n,sha256:h2});
}
const out={passed:true,total_returned_improve:result.reduce((a,r)=>a+r.returned_improve,0),cohorts:result,
 finding:'All matched returned Improve prompts include the exact complete parent. No evidence here of missing parent input.',
 correction:'V1 inspected later Analyze prompts too. Its all-prompts flag is not a missing-parent measure; preserved and superseded by role-specific V2.',
 limits:['Recorded client prompts only, not all attempts/server capture. No inference that fixed five-fold wording caused failure.',
 'No prompt intervention or revision of original comparison gates. Independent aggregation, not independent raw-journal extraction.']};
console.log(JSON.stringify(out,null,2));
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(out,null,2)+'\n',{flag:'wx'});
