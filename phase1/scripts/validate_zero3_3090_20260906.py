"""Separate portability profile; does not qualify the production PRO6000 pivot."""
from phase1.scripts.validate_zero3_session_gpu_20260905 import main

if __name__ == '__main__':
    main(expected_gpu='RTX 3090')
