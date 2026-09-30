"""Validate only this parser-fix publication and its exact artifact links."""
import argparse,hashlib,json,re
from pathlib import Path

SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')
ASSIGN=re.compile(rb'(?i)["\x27](?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)["\x27]\s*:\s*["\x27](?!\s*["\x27])[^"\x27]{12,}["\x27]')
PRIVATE={'code','prompt','term_out','terminal_output','original_plan','repair_plans','candidate_identity','candidate_profile','private_selection','api_key','access_token','password','secret'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def check_keys(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            assert k.lower() not in PRIVATE, 'private schema field'
            check_keys(v)
    elif isinstance(obj,list):
        for x in obj:check_keys(x)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    r=a.root/'phase1/results/comparison_0930_parser_20261001'
    s=a.root/'phase1/scripts/comparison_0930_parser'
    b=a.root/'phase1/patches/python_fence_parser_20261001'
    selected=sorted(p for base in (r,s,b) for p in base.rglob('*') if p.is_file() and p.name!='manifest.json')
    selected += [a.root/'.gitattributes',a.root/'phase1/CURRENT_DIRECTION.md',
                 a.root/'phase1/results/comparison_0930_feedback_diagnostic_20261001/manifest.json']
    hashes={};total=0
    for p in selected:
        assert not p.is_symlink() and p.suffix!='.pyc'
        raw=p.read_bytes();assert len(raw)<8*1024**2
        assert not SECRET.search(raw) and not ASSIGN.search(raw),'credential-shaped content'
        if p.suffix=='.json':check_keys(json.loads(raw))
        hashes[p.relative_to(a.root).as_posix()]=sha(p);total+=len(raw)
    def read(name):return json.loads((r/name).read_text())
    links=[('compiler_census.json','script_sha256','compiler_feedback_census_0930.py'),
           ('fence_replay.json','script_sha256','fence_replay_0930.py'),
           ('rejection_chains.json','script_sha256','parser_rejection_chains_0930.py'),
           ('source_provenance.json','script_sha256','parser_source_provenance_0930.py'),
           ('lexical_context.json','script_sha256','parser_lexical_context_0930.py'),
           ('apply_receipt.json','script_sha256','build_parser_fix_patch_0930.py'),
           ('regression_receipt.json','runner_sha256','run_parser_regression_0930.py'),
           ('native_independent.json','verifier_sha256','verify_native_parser_replay_resumable_0930.py')]
    for name,key,script in links:assert read(name)[key]==sha(s/script),script
    native=read('native_independent.json');assert native['status']=='PASS'
    assert native['counts']=={'actions':983,'previously_admitted_ast_preserved':779,
        'rejected_recovered_without_program_edit':204,'independent_shield_restore_ast_matches':204}
    for path,pin in native['package_file_sha256'].items():assert sha(b/path)==pin,path
    regression=read('regression_receipt.json')
    assert regression['status']=='PASS' and regression['tests_run']==17 and regression['skipped']==0
    assert regression['source_file_sha256']==native['package_file_sha256']
    apply=read('apply_receipt.json');assert apply['status']=='PASS'
    assert apply['patch_sha256']==sha(b/'fix_python_fences.patch')
    for path,pin in apply['post_apply_file_sha256'].items():assert sha(b/'candidate'/path)==pin
    sources={x['run_digest']:x['journal_sha256'] for x in native['sources']}
    assert len(sources)==39
    asts={(sources[x['run_digest']],x['segment'],x['step']):x['accepted_ast_sha256'] for x in native['rows'] if not x['old_admitted']}
    lexical=read('lexical_context.json');assert lexical['rejected_responses_checked']==204
    for x in lexical['rows']:assert asts[(x['journal_sha256'],x['segment'],x['step'])]==x['accepted_ast_sha256']
    fence=read('fence_replay.json');assert len(fence['rows'])==983
    key=lambda x:(x['run_digest'],x['segment'],x['step'])
    assert {key(x):x['native_generic_reject'] for x in fence['rows']}=={key(x):not x['old_admitted'] for x in native['rows']}
    old=a.root/'phase1/results/comparison_0930_feedback_diagnostic_20261001/manifest.json'
    for path,pin in json.loads(old.read_text())['files'].items():assert sha(a.root/path)==pin, path
    result={'status':'PASS','files_scanned':len(selected),'bytes_scanned':total,'credential_hits':0,
            'private_payload_fields':0,'artifact_script_links':len(links),'raw_native_lexical_join_rows':len(asts),
            'old_package_manifest_valid':True,'files':hashes,
            'scanner_sha256':sha(Path(__file__))}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))


if __name__=='__main__':main()
