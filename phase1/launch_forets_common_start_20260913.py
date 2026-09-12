"""Reuse once-only native launcher with the new exact matrix and common config."""
import argparse
from pathlib import Path
import build_forets_single_vote_20260913 as prior
import build_forets_common_start_20260913 as current
import launch_forets_single_vote_20260913 as launcher
from forets_environment_build_20260912 import read

original = launcher.checked


def checked(root):
    prior.order = current.order
    value = original(root)
    proof = read(root/'common-start-integration.json')
    if proof['status'] != 'PASS_SYNTHETIC_NOT_REAL_TASK_RESULT' or proof['source_tree'] != value[0]['source_tree']:
        raise ValueError('common-start path integration not complete')
    for row in value[1]['run_configs']:
        cfg = read(root/'configs'/(row['run_id']+'.json'), row['config_sha256'])
        if cfg['solver']['common_start_protocol'] != 'rf_common_v1':
            raise ValueError('shared starting program not configured')
    return value


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('route','submit'));p.add_argument('root',type=Path)
    a=p.parse_args();launcher.checked=checked;getattr(launcher,a.mode)(a.root)
