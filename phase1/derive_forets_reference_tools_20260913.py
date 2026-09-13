"""Mechanical fixed-seed successor readers; never changes the live old stage."""
import argparse
from pathlib import Path
from forets_environment_build_20260912 import write, encode, sha
from forets_paid_patch_20260911 import once


def derive(output):
    base=Path(__file__).resolve().parent
    output.mkdir(exist_ok=False)
    names={
        'readout_forets_branching_20260913.py':'readout_forets_reference_20260913.py',
        'readout_forets_branching_core_20260913.py':'readout_forets_reference_core_20260913.py',
        'readout_forets_single_vote_20260913.py':'readout_forets_reference_cost_20260913.py',
        'launch_forets_branching_20260913.py':'launch_forets_reference_20260913.py'}
    evidence={}
    for old,new in names.items():
        raw=(base/old).read_bytes();text=raw.decode()
        for before,after in names.items():text=text.replace(before,after).replace(before[:-3],after[:-3])
        if 'readout_forets_branching' in old:
            text=text.replace('(30,31)','(32,33)')
        if old=='readout_forets_single_vote_20260913.py':
            text=once(text,"finished['observed_task_outcomes'] is not False",
                "finished['observed_candidate_outcomes'] is not False or finished['observed_reference_feedback'] is not True")
        if old=='readout_forets_branching_20260913.py':
            text=once(text,"'verify_forets_review_selection_20260912.py')",
                "'verify_forets_review_selection_20260912.py','verify_forets_reference_records_20260913.py')")
            text=once(text,"            checked=verify_pool(value,cfg['solver'],r,inp,done)",
                "            checked=verify_pool(value,cfg['solver'],r,inp,done)\n"
                "            if done is not None:\n"
                "                from verify_forets_reference_records_20260913 import verify_reference\n"
                "                verify_reference(value,checkpoint,rank,inp,done)")
        if old=='launch_forets_branching_20260913.py':
            text=text.replace('from build_forets_branching_20260913 import order','from build_forets_reference_20260913 import order')
            text=once(text,"branch=read(root/'branching-integration.json')","branch=read(root/'reference-integration.json')")
        compile(text,new,'exec');written=text.encode()
        write(output/new,written);evidence[new]=dict(base_file=old,base_sha256=sha(raw),derived_sha256=sha(written))
    write(output/'derivation.json',encode(evidence))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);derive(p.parse_args().output)
