"""Independent 2-versus-4 live challenge; never a replacement for v7.

Fixed before v7 outcome readout. Submit only if v7 infrastructure completes and
the separately frozen neural width study preserves outputs/steps for all36.
No decision based on whether either earlier study reports a favorable effect.
New seeds; original tasks, budgets, images and native MCTS unchanged.
"""
import sys
import live_entry_fix_trial
from lifecycle_pilot import read,sha

trial=live_entry_fix_trial.trial
trial.R=trial.B/'scheduling-live-width-20261009-v1'
trial.NAME='live_width_challenge.py'
trial.SEED_BASE=144901
trial.ADMISSION_LIMITS={'share2':2,'share4':4}
trial.FILES=(trial.NAME,)+trial.FILES


def host():return trial.host()


def prerequisites():
    live=trial.B/'scheduling-live-search-20261009-v7'
    neural=trial.B/'scheduling-neural-width-20261009-v1'
    a=read(live/'readout-v1/summary.json');b=read(neural/'readout-v1/summary.json')
    if a['plan_sha256']!='86aa8f7a3d534ef1eaaa5475482a8838fe29c06f1ee30cb367cc05aae411c774':
        raise ValueError('wrong prerequisite live batch')
    if b['source_commit']!='4a19588cb24cea8ed1d1b91f563d4ed06a68f4af':
        raise ValueError('wrong prerequisite neural study')
    for root,result in ((live,a),(neural,b)):
        if sha(root/'plan.json')!=result['plan_sha256'] or sha(root/'closed.json')!=result['closed_sha256']:
            raise ValueError('prerequisite identity drift')
    if a['complete']!=16 or not a['structural_audit'] or a['controller_error'] is not None:
        raise ValueError('live execution integrity not passed')
    if b['complete']!=36 or not b['complete_valid_comparison']:
        raise ValueError('neural correctness/coverage not passed')
    # Effect values deliberately are not inspected. These immutable hashes are
    # embedded in the new plan and checked by every native process thereafter.
    trial.PREREQUISITE_RECEIPTS={str(root/'readout-v1/summary.json'):sha(root/'readout-v1/summary.json')
        for root in (live,neural)}


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1] in ('prepare','submit'):prerequisites()
    sys.exit(trial.main())
