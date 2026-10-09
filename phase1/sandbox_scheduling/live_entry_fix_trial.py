"""V7 fixes only the wrapper's exported host interface, before any outcomes.

V6 failed qualification before GPU arithmetic, model load or candidates. Its
16 assignments and 42 GPU-second cost remain recorded. All scientific knobs
and V6 seeds are retained; this is an infrastructure retry, not new replication.
"""
import sys
import live_physical_cpu_trial

trial=live_physical_cpu_trial.trial
trial.R=trial.B/'scheduling-live-search-20261009-v7'
trial.NAME='live_entry_fix_trial.py'
trial.FILES=(trial.NAME,)+trial.FILES


def host():
    return trial.host()


if __name__=='__main__':sys.exit(trial.main())
