"""Same terminal-only grading and independent numerical checks for depth two."""
import argparse
from pathlib import Path
import readout_comparison_live_debug_20260919 as reader
from run_comparison_depth2_execute_20260919 import check

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    reader.check=check
    reader.main(args.root)
