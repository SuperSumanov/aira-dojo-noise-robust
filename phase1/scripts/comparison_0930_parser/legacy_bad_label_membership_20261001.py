"""Read only recorded training membership for the one legacy unknown-execution row."""
import argparse,hashlib,json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    case=json.loads(a.case.read_text());assert case['status']=='FIXED_SINGLE_ROW_REPLAY'
    assert len(case['rows'])==1;row=case['rows'][0]
    root=Path('/research/d7/spc/yzyang4/proposal-risk-transfer-20260928-v1')
    raw=(root/'folds.json').read_bytes();folds=json.loads(raw);assert len(folds)==9
    rows=[]
    for fold in folds:
        train_run=row['run_digest'] in fold['train_runs']
        heldout_run=row['run_digest'] in fold['heldout_runs']
        assert train_run != heldout_run
        input_retained=row['input_20000_sha256'] in fold['train_inputs']
        included=train_run and input_retained
        rows.append({'fold':fold['fold'],'source_run_in_train':train_run,'source_run_heldout':heldout_run,
                     'input_hash_in_train':input_retained,'bad_debug_row_in_repair_and_mixed_training':included})
    result={'status':'TRAINING_MEMBERSHIP_ONLY','folds_checked':len(rows),'row_digest':row['row_digest'],
            'rows':rows,'affected_folds':sum(r['bad_debug_row_in_repair_and_mixed_training'] for r in rows),
            'potentially_affected_fitted_models':2*sum(r['bad_debug_row_in_repair_and_mixed_training'] for r in rows),
            'folds_sha256':hashlib.sha256(raw).hexdigest(),'case_sha256':hashlib.sha256(a.case.read_bytes()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'boundary':'Only the original 36-fit study: repair/mixed fit membership, not influence magnitude or sign. Derived prior adjustments may also change; later matched/contrast studies not enumerated. No model files, prediction values, metrics or refits.'}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'status':'FAILED_CLOSED','type':type(e).__name__}));raise SystemExit(2)
