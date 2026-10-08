"""Pre-submission replacement: usable local 27B, same admission comparison.

The prepared 9B v1 was withdrawn before any GPU allocation, following historical
eligibility review (base native valid0/4). This is not a seed/result rescue.
"""
import sys
import live_search_trial_20261009 as trial

trial.R=trial.B/'scheduling-live-search-20261009-v2'
trial.NAME='live_27b_trial.py'
trial.PROFILE='27b'
trial.MODEL_ID='qwen3.8-27b'
trial.MODEL_DIR=trial.B/'local-qwen27b-20260914-zcx1k1dy/model'
trial.FILES=('live_27b_trial.py','live_search_trial_20261009.py','live_admission.py',
             'live_runtime_hooks.py','bounded_readiness.py','lifecycle_pilot.py','live_readout.py')

def host():return trial.host()

if __name__=='__main__':sys.exit(trial.main())
