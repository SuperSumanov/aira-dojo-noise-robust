"""Pinned second-repair execution; reuse the unchanged full-task worker."""
import argparse, os
from pathlib import Path
import run_comparison_live_debug_execute_20260919 as execution

def configure():
    execution.GEN=execution.BASE/'comparison-depth2-debug-20260919-ffunn8gg'
    execution.GEN_PREPARED='217f72c4c0a4a6e421538a265d7208e714c9ec07570afb47424408b29cd7db06'
    execution.ROOT_PREFIX='comparison-depth2-debug-exec-20260919-'
    execution.REQUEST_SEEDS=[601,602]
    execution.SCRIPT=Path(__file__).name
    execution.READER='readout_comparison_depth2_20260919.py'
    execution.CONTEXT_MODULE='run_comparison_depth2_execute_20260919'
    execution.EXTRA_FILES=('run_comparison_live_debug_execute_20260919.py','readout_comparison_live_debug_20260919.py')

def check(root):
    configure();return execution.check(root)

def binding_context(env):
    configure();return execution.binding_context(env)

if __name__=='__main__':
    os.umask(0o077);configure()
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','coordinate','execute'])
    parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--index',type=int);args=parser.parse_args()
    if args.mode=='prepare':execution.prepare(args.commit)
    elif args.mode=='execute':execution.execute(args.root,args.index)
    else:getattr(execution,args.mode)(args.root)
