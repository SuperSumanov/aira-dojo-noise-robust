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
           ('native_independent.json','verifier_sha256','verify_native_parser_replay_resumable_0930.py'),
           ('legacy_label_audit.json','script_sha256','audit_legacy_exit_labels_20261001.py'),
           ('legacy_one_parser_replay.json','script_sha256','check_one_legacy_rejection_20261001.py'),
           ('legacy_training_membership.json','script_sha256','legacy_bad_label_membership_20261001.py'),
           ('contract_matrix.json','script_sha256','parser_contract_matrix_20261001.py'),
           ('label_route.json','script_sha256','parser_label_route_20261001.py'),
           ('published_d11beb74_readback.json','script_sha256','verify_published_package_20261001.py')]
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
    legacy=read('legacy_label_audit.json'); rows=legacy['row_flags']
    assert legacy['runs']==25 and legacy['rows']==len(rows)==547
    assert len({x['row_digest'] for x in rows})==547
    assert len({x['run_digest'] for x in rows})==25
    assert {k:sum(x[k] for x in rows) for k in legacy['totals']}==legacy['totals']
    assert all(type(x[k]) is bool for x in rows for k in legacy['totals'])
    for group in legacy['by_task_role']:
        subset=[x for x in rows if x['task']==group['task'] and
                (x['operator']=='debug')==(group['role']=='debug')]
        assert len(subset)==group['rows']
        for k in legacy['totals']:assert sum(x[k] for x in subset)==group[k]
    for group in legacy['per_run']:
        subset=[x for x in rows if x['run_digest']==group['run_digest']]
        original=[x for x in subset if x['operator']!='debug']
        assert len(subset)==group['rows'] and len(original)==group['original_rows']
        assert sum(x['exit_zero'] for x in original)==group['original_exit_zero']
        for k in legacy['totals']:assert sum(x[k] for x in subset)==group[k]
    original=[x for x in rows if x['operator']!='debug']
    assert len(original)==legacy['original_rows']==240
    assert sum(x['exit_zero'] for x in original)==103
    assert not any(x['generic_rejection_labeled_positive'] for x in original)
    bad=[x for x in rows if x['generic_rejection_labeled_positive']]
    assert len(bad)==1 and bad[0]['operator']=='debug' and bad[0]['zero_duration']
    case=read('legacy_one_parser_replay.json'); assert len(case['rows'])==1
    item=case['rows'][0]; assert item['row_digest']==bad[0]['row_digest']
    assert not item['old_admitted'] and not item['new_admitted']
    for path,pin in case['package_hashes'].items():assert sha(b/path)==pin
    sources={x['run_digest']:x['journal_sha256'] for x in legacy['sources']}
    assert sources[item['run_digest']]==item['journal_sha256']
    membership=read('legacy_training_membership.json')
    assert membership['case_sha256']==sha(r/'legacy_one_parser_replay.json')
    assert membership['row_digest']==item['row_digest']
    assert len(membership['rows'])==membership['folds_checked']==9
    included=0
    for fold in membership['rows']:
        assert fold['source_run_in_train'] != fold['source_run_heldout']
        retained=fold['source_run_in_train'] and fold['input_hash_in_train']
        assert retained==fold['bad_debug_row_in_repair_and_mixed_training']
        included+=retained
    assert included==membership['affected_folds']==7
    assert 2*included==membership['potentially_affected_fitted_models']==14
    matrix=read('contract_matrix.json')
    assert matrix['cases']==len(matrix['rows'])==60
    assert matrix['contract_checks_passed']==sum(x['new_contract_met'] for x in matrix['rows'])==60
    assert matrix['old_admitted_new_rejected']==sum(x['old']['task_admitted'] and not x['new']['task_admitted'] for x in matrix['rows'])==12
    assert matrix['new_admitted_wrong_ast']==sum(x['new']['task_admitted'] and not x['new']['intended_ast_preserved'] for x in matrix['rows'])==0
    for x in matrix['rows']:
        condition=(x['new']['task_admitted'] and x['new']['intended_ast_preserved']) if x['expected_new_contract']=='intended_ast' else not x['new']['task_admitted']
        assert condition==x['new_contract_met']
    for path,pin in matrix['bundle_sha256'].items():assert sha(b/path)==pin
    route=read('label_route.json')
    assert len(route['rows'])==route['rows_checked']==204
    assert route['input_sha256']['compiler_census.json']==sha(r/'compiler_census.json')
    trace=a.root/'phase1/results/comparison_0930_feedback_diagnostic_20261001/numeric_trace.json'
    assert route['input_sha256']['numeric_trace.json']==sha(trace)
    expected_rejects={key(x) for x in fence['rows'] if x['native_generic_reject']}
    assert {key(x) for x in route['rows']}==expected_rejects
    assert {k:sum(bool(x[k]) for x in route['rows']) for k in route['counts']}==route['counts']
    assert route['counts']=={'score_missing':204,'grade_nonfinite':0,'valid':0,'buggy':204,'exit_zero':204,'execution_zero':204}
    readback=read('published_d11beb74_readback.json')
    assert readback['status']=='PASS' and readback['source_commit']=='d11beb748f1f1fa654a88debd03b64f6457fbdfa'
    assert readback['manifest_exact_match'] and readback['contract_matrix_exact_match']
    assert readback['native_regression_tests']==17 and len(readback['commands'])==5
    assert all(x['returncode']==0 for x in readback['commands'])
    old=a.root/'phase1/results/comparison_0930_feedback_diagnostic_20261001/manifest.json'
    for path,pin in json.loads(old.read_text())['files'].items():assert sha(a.root/path)==pin, path
    result={'status':'PASS','files_scanned':len(selected),'bytes_scanned':total,'credential_hits':0,
            'private_payload_fields':0,'artifact_script_links':len(links),'raw_native_lexical_join_rows':len(asts),
            'legacy_audit_rows':len(rows),'legacy_unknown_execution_rows':len(bad),
            'legacy_training_membership_folds':included,
            'synthetic_contract_cases':matrix['cases'],'stricter_rejection_cases':matrix['old_admitted_new_rejected'],
            'missing_score_route_rows':route['rows_checked'],'published_d11beb74_readback_valid':True,
            'old_package_manifest_valid':True,'files':hashes,
            'scanner_sha256':sha(Path(__file__))}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))


if __name__=='__main__':main()
