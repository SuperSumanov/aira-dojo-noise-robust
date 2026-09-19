"""Same closed readout on the independently named third-prefix matrix."""
import argparse
from pathlib import Path
import readout_comparison_reuse_20260919 as reader
from run_comparison_third_bank_20260919 import prepared,driver,RUN
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    p=prepared(args.root);receipt=p['extension_context']
    if receipt['source_run']!=RUN:raise ValueError('prefix identity')
    reader.prepared=prepared;reader.SEEDS=(3,);reader.PREFIX_ERRORS={3:receipt['historical_prefix_error']}
    reader.main(args.root)
