"""Summarize immutable descriptive inputs without outcome-dependent choices."""
import argparse,hashlib,json,math,statistics
from pathlib import Path

def describe(x):
    return {'n':len(x),'mean':statistics.mean(x) if x else None,'median':statistics.median(x) if x else None,
            'sd':statistics.stdev(x) if len(x)>1 else None}

def group(rows):
    seconds=math.fsum(r['execution_seconds'] for r in rows)
    debug=math.fsum(r['debug_execution_seconds'] for r in rows)
    return {'run_directories':len(rows),'root_segments':sum(r['restart_segments'] for r in rows),
      'events':sum(r['events'] for r in rows),'original_actions':sum(r['original_actions'] for r in rows),
      'original_finite_grade':sum(r['original_finite_grade'] for r in rows),'debug_actions':sum(r['debug_actions'] for r in rows),
      'last_choice_finite_grade':sum(r['chosen_has_finite_grade'] for r in rows),
      'last_choice_is_debug':sum(r['last_chosen_operator']=='debug' and r['chosen_has_finite_grade'] for r in rows),
      'last_choice_finite_origin_ungraded':sum(r['chosen_has_finite_grade'] and r['chosen_source_original_had_grade'] is False for r in rows),
      'measurable_replacements':sum(r['measurable_replacements'] for r in rows),
      'external_regressions':sum(r['external_regressions_on_replacement'] for r in rows),
      'run_directories_with_external_regression':sum(r['external_regressions_on_replacement']>0 for r in rows),
      'observed_chains_first_ungraded_later_graded':sum(r['observed_chains_first_ungraded_later_graded'] for r in rows),
      'execution_seconds':seconds,'debug_execution_seconds':debug,'pooled_debug_execution_share':debug/seconds if seconds else None,
      'per_run_debug_execution_share':describe([r['debug_execution_seconds']/r['execution_seconds'] for r in rows if r['execution_seconds']>0])}

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw-receipt',type=Path,required=True);p.add_argument('--syntax',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=json.loads(a.raw_receipt.read_text());syntax=json.loads(a.syntax.read_text());rows=raw['rows']
    assert len(rows)==len({r['run_digest'] for r in rows})==39
    source={r['run_digest']:r for r in raw['sources']}
    assert len(syntax['sources'])==39
    for r in syntax['sources']:
        assert r['journal_sha256']==source[r['run_digest']]['journal_sha256']
        assert r['config_sha256']==source[r['run_digest']]['config_sha256']
    sg=[]
    for task in sorted({r['task'] for r in rows}):
        for endpoint in ('first_finite_grade_debug','last_logged_debug'):
            rr=[r for r in syntax['rows'] if r['task']==task and r['endpoint']==endpoint]
            usable=[r for r in rr if r['usable_ast']];novel=[r for r in usable if r['novel_call_targets']>0]
            sg.append({'task':task,'endpoint':endpoint,'all_chains':len(rr),'usable_ast':len(usable),
              'exact_ast_revert_to_parent':sum(r['exact_ast_revert_to_parent'] for r in usable),
              'has_novel_call_targets':len(novel),'all_novel_call_targets_absent':sum(r['retained_call_targets']==0 for r in novel),
              'some_novel_call_targets_absent':sum(r['retained_call_targets']<r['novel_call_targets'] for r in novel),
              'retained_fraction':describe([r['retained_call_targets']/r['novel_call_targets'] for r in novel])})
    result={'kind':'EXPLORATORY_ARCHIVE_DIAGNOSTIC_NOT_METHOD_BENEFIT','all':group(rows),
      'by_task':{task:group([r for r in rows if r['task']==task]) for task in sorted({r['task'] for r in rows})},
      'syntax':{'raw_parse_coverage':syntax['statistics'],'groups':sg},
      'input_sha256':{'raw_receipt':hashlib.sha256(a.raw_receipt.read_bytes()).hexdigest(),'syntax':hashlib.sha256(a.syntax.read_bytes()).hexdigest()},
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'limitations':['Run directories are not independently certified physical runs.','Last logged native choices are not certified final deliveries.',
        'Execution seconds exclude generation and other search overhead.','Syntax disappearance is not semantic intent loss.',
        'Successful repair endpoints are a selected subset; no causal repair effect.', 'Scores are descriptive only, never training or controller feedback.']}
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({'all':result['all'],'syntax_groups':sg}))

if __name__=='__main__':main()
