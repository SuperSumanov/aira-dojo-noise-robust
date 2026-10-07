"""Notebook-to-standalone-script invocation boundary; no candidate edits.

Not deployed to closed job16846. A future allocation needs its own frozen plan.
The kernel's connection arguments are interpreter plumbing, not candidate flags.
Only default script invocation is authorized here (no --debug/fast settings).
"""

SCRIPT_ENTRY = "import sys as _r14_sys\n_r14_sys.argv = ['candidate.py']\n"


def setup_cell(seed, instrumentation=''):
    if type(seed) is not int or seed<0:raise ValueError('nonnegative integer seed required')
    return SCRIPT_ENTRY+f'import random,numpy as np\nrandom.seed({seed});np.random.seed({seed})\n'+instrumentation
