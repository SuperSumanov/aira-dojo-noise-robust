"""Fixed original second-selected drafts, not best-of-pool or new sampling."""
import argparse,os
from pathlib import Path
import run_comparison_pizza_prefix_20260919 as driver

def configure():
    driver.SCRIPT=Path(__file__).name;driver.ROOT_PREFIX='comparison-pizza-selected-second-20260919-'
    driver.SELECT_SECOND=True;driver.PLAN='comparison_pizza_selected_second_plan_20260919.json'
    driver.ALLOWED_JOBS={'12535','14165'}

def binding_context(env):configure();return driver.binding_context(env)

if __name__=='__main__':
    os.umask(0o077);configure();parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','coordinate','execute']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--index',type=int);args=parser.parse_args()
    if args.mode=='prepare':driver.prepare(args.commit)
    elif args.mode=='execute':driver.execute(args.root,args.index)
    else:getattr(driver,args.mode)(args.root)
