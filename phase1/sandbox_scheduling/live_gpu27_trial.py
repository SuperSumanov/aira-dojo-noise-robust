"""New v4 placement after user-approved GPU migration on 2026-10-09.

V3 failed before any model or candidate launch on gpu24. Preserve its records.
Same frozen 27B science/matrix/budget; qualify the original image on gpu27
inside this allocation before loading the generator. No fallback to CPU.
"""
import sys
import live_27b_trial

trial = live_27b_trial.trial
trial.R = trial.B / 'scheduling-live-search-20261009-v4'
trial.NAME = 'live_gpu27_trial.py'
trial.NODE = 'gpu27'
trial.NODE_QUALIFICATION = True
trial.FILES = ('live_gpu27_trial.py', 'live_node_qualification.py') + trial.FILES


def host():
    return trial.host()


if __name__ == '__main__':
    sys.exit(trial.main())
