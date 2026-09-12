"""Exact post-terminal seed15 binding; no replay or model call."""
from pathlib import Path
import verify_forets_context_e2e_20260912 as verifier


def bind():
    verifier.ROOT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-3no2iopd')
    verifier.JOB='13128'
    verifier.PREPARED='883062309b6edeee43ac93be26042c9376279ab712948e034bceb39dc67dae1e'
    verifier.TREE='54e353963a6899965896b2e8ea492207829b3cbd'
    verifier.AUTH='c623a0236a59df74f9dac1f3641ea724c9f2fdece7266c23aa604e6aaab1bb5e'
    verifier.SEED=15
    verifier.MIN_CALLS=286
    verifier.MAX_ACCOUNTED_NANO=5907137235
    verifier.EXPECTED_SKIP=True
    return verifier


if __name__=='__main__':bind().main()
