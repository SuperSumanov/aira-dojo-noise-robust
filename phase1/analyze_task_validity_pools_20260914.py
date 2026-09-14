"""Same old-target-only diagnostic for the completed task-feature comparison."""
from pathlib import Path
import analyze_legacy_validity_pools_20260914 as analysis
if __name__=='__main__':
    analysis.ROOT=Path('/research/d7/spc/yzyang4/forets-task-validity-20260914-n8q3h72y')
    analysis.SUMMARY_SHA='66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33'
    analysis.main()
