"""Fail closed if gpu28 lacks the unchanged R5 CUDA toolchain."""
from phase1.check_g0_r5_build_tools import main

if __name__ == '__main__':
    main(expected_host='gpu28')
