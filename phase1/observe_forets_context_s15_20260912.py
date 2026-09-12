"""Explicit read-only in-session observer for the seed15 replication."""
import argparse
from pathlib import Path
import observe_forets_context_e2e_20260912 as observer


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    observer.ROOT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-3no2iopd')
    observer.main(args.watch)
