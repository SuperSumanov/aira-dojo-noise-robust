"""Independent supplement check: missing replies stay missing, failed execution cannot win."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
import verify_comparison_native_selection_20260920 as independent

def main(folder):
    primary_path=folder/'summary.json';supplement_path=folder/'decision-identification.json'
    primary_raw=primary_path.read_bytes();primary=json.loads(primary_raw);supplement=json.loads(supplement_path.read_bytes())
    if hashlib.sha256(primary_raw).hexdigest()!=supplement['primary_summary_sha256'] or primary['rows']!=supplement['original_rows']:raise ValueError('original data not preserved')
    if primary['status']!='INCOMPLETE_NO_POINT_EFFECT_CLAIM' or supplement['primary_status_unchanged']!=primary['status']:raise ValueError('original status changed')
    if supplement['new_model_calls'] or supplement['new_program_executions'] or supplement['additional_gpu_hours']:raise ValueError('new observations forbidden')
    rows=copy.deepcopy(primary['rows']);missing=[r for r in rows if r['analysis_status']!='returned']
    if len(missing)!=1 or missing[0]['task']!='spooky-author-identification' or missing[0]['seed']!=2 or missing[0]['slot']!=4 or missing[0]['exit_code']!=1:raise ValueError('exact closed missing case')
    with patch.object(independent.native,'COMMIT',independent.SOURCE_COMMIT):parser,parser_sha=independent.native.native_parser()
    hook=independent.submission_hook();trials=0
    # Complement the exact OR-gate certificate with maximally favorable and
    # unfavorable replies through the independently extracted real parser.
    for bug in (True,False):
        for metric in (None,-1e100,0.,1e100):
            with patch.dict(sys.modules,{'dojo.solvers.fore_ts.wallclock':hook}):
                accepted=independent.native.decide(parser,is_bug=bug,metric=metric,exit_code=1,valid_guard=None)
            if accepted:raise ValueError('missing reply can affect selection')
            trials+=1
    r=missing[0];r.update(analysis_status='returned',native_accepted=False,native_metric=None,native_is_bug=False)
    derived=copy.deepcopy(supplement);derived.update(rows=rows,training=False,paid_api_calls=0,gpu_hours=primary['gpu_hours'],allocation_seconds=primary['allocation_seconds'])
    base=Path(__file__).parent/'results';labels=[]
    for name,digest,seeds in [('comparison_pool_20260919/combined/summary.json','41e42fbff91ca970e8f5ee19a1ffdf57c31ffe0ddd6a24182e5e304c1225ef4f',(1,2,3)),('comparison_spooky_pool_20260919/summary.json','721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1',(1,2))]:
        raw=(base/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('closed local source')
        labels.extend(row for row in json.loads(raw)['rows'] if row['seed'] in seeds)
    reward_raw=(base/'comparison_frozen_reward_20260919/summary.json').read_bytes()
    if hashlib.sha256(reward_raw).hexdigest()!=primary['reward_summary_sha256']:raise ValueError('frozen reward source')
    result=independent.verify(derived,json.loads(reward_raw),labels)
    result.update(supplement_sha256=hashlib.sha256(supplement_path.read_bytes()).hexdigest(),primary_sha256=hashlib.sha256(primary_raw).hexdigest(),
        missing_analysis_responses_still=1,decision_invariance_cases=trials,parser_sha256=parser_sha,original_unmodified=True)
    with (folder/'identification-independent-check.json').open('x') as file:json.dump(result,file,indent=2)
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);main(p.parse_args().folder)
