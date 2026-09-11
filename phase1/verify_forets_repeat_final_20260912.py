"""Independent seed12 closeout, only after job13118 and its primary report end.

Uses the unchanged selected-node/external-grade check, not numerical regrading.
Do not use this wrapper on seed11 or any protected evaluation cohort.
"""
from pathlib import Path
import verify_forets_review_final_20260912 as verifier

verifier.ROOT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-zuvnt3oa')
verifier.JOB='13118'
verifier.PREPARED='963418d10d5645f7401a85da42d6fc3d5b2f7553e76cf44eecbeb342f17d44d5'
verifier.TREE='35711518b3b7262bccd3bebfdd2b4a4b7c726715'
verifier.CARRIED_ROWS=117
verifier.MAX_ACCOUNTED_NANO=3274500927

if __name__=='__main__':verifier.main()
