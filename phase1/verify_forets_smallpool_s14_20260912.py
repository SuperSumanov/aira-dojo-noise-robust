"""Exact seed14 verification binding; no readout until the entire block closes."""
from pathlib import Path
import verify_forets_context_e2e_20260912 as verifier


def bind():
    verifier.ROOT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-x3pkniqp')
    verifier.JOB='13124'
    verifier.PREPARED='111a28c1c12174c00451c737435028cf8528b386fea1f723392a34e648d6f40e'
    verifier.TREE='f70eb4859c48c61bba37b298fbf8e32e367644ae'
    verifier.AUTH='d42e129a04210bd56c981c393d2890e0b50b1d98755027893ad3fa6c3127e93a'
    verifier.SEED=14
    verifier.MIN_CALLS=216  # all 214 carried entries + two settled route checks
    verifier.MAX_ACCOUNTED_NANO=5714760245
    verifier.EXPECTED_SKIP=True
    return verifier


if __name__=='__main__':bind().main()
