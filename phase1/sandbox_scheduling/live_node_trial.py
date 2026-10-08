"""Pre-execution placement migration to same-model RTX3090 gpu24.

V2 job17229 was cancelled before allocation, after finding per-step port reuse
and a start estimate outside the window. Original root/receipt remain intact.
No task/seed/model/budget change, and no scientific outcome existed in v2.
"""
import sys
import live_27b_trial

trial=live_27b_trial.trial
trial.R=trial.B/'scheduling-live-search-20261009-v3'
trial.NAME='live_node_trial.py'
trial.NODE='gpu24'
trial.NODE_QUALIFICATION=True
trial.FILES=('live_node_trial.py','live_node_qualification.py')+trial.FILES

def host():return trial.host()

if __name__=='__main__':sys.exit(trial.main())
