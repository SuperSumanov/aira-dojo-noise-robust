"""Independent v5: unfiltered live scheduling at fixed whole-pool budgets.

V4 remains a failed, closed eligibility-gated pilot. This does not resume it or
replace its denominator. New seeds, all 16 assignments regardless of model
success; stop only on safety/infrastructure failure. Invalid endpoints remain
invalid, not zero-valued scores. Four 1320s reserved slots include service start,
600s search, cleanup and explicit idle padding, identical across both arms.
"""
import sys
import live_27b_trial

trial = live_27b_trial.trial
trial.R = trial.B / 'scheduling-live-search-20261009-v5'
trial.NAME = 'live_fixed_budget_trial.py'
trial.NODE = 'gpu27'
trial.NODE_QUALIFICATION = True
trial.SEED_BASE = 141901
trial.GENERATOR_ELIGIBILITY_GATE = False
trial.FIXED_BLOCK_SECONDS = 1320
trial.FILES = ('live_fixed_budget_trial.py','live_node_qualification.py') + trial.FILES


def host():
    return trial.host()


if __name__ == '__main__':
    sys.exit(trial.main())
