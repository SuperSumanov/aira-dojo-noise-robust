"""Independent v6 after the zero-candidate v5 CPU-contract failure.

Identical unfiltered16-run fixed-budget question; standard Slurm hint requests
18 usable physical cores. Service12/execution6 topology is checked before use.
V5 remains closed/cancelled, not overwritten or included in effect estimation.
"""
import sys
import live_fixed_budget_trial

trial=live_fixed_budget_trial.trial
trial.R=trial.B/'scheduling-live-search-20261009-v6'
trial.NAME='live_physical_cpu_trial.py'
trial.PHYSICAL_CPU_BINDING=True
trial.SEED_BASE=142901
trial.FILES=(trial.NAME,)+trial.FILES

if __name__=='__main__':sys.exit(trial.main())
