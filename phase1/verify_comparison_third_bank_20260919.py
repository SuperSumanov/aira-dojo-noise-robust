"""Independent full path/statistic verification for the fixed third prefix."""
import argparse,hashlib,json
from pathlib import Path
from verify_comparison_reuse_results_20260919 import verify
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('summary',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    raw=args.summary.read_bytes();summary=json.loads(raw)
    if {r['run'] for r in summary['rows']}!={'e4a4275f2df8028e'}:raise ValueError('source run')
    result=verify(summary,expected_seeds=(3,));result['source_summary_sha256']=hashlib.sha256(raw).hexdigest()
    with args.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result,indent=2))
