"""Seed12-only post-terminal selector/code-contrast check; no online changes."""
from pathlib import Path
import verify_forets_review_selection_20260912 as verifier

verifier.ROOT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-zuvnt3oa')
verifier.PREPARED='963418d10d5645f7401a85da42d6fc3d5b2f7553e76cf44eecbeb342f17d44d5'
verifier.SEED=12

if __name__=='__main__':verifier.main()
