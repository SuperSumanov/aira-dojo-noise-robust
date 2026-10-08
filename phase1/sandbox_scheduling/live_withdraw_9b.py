"""Irreversible one-shot submission blocker for the unexecuted v1 preparation."""
import datetime
from pathlib import Path
from lifecycle_pilot import read,write,sha

R=Path('/research/d7/spc/yzyang4/scheduling-live-search-20261009-v1')
PIN='d42f1440ef8a98d3476aa465f6e94fc16c7c3242f318adf3afc1eb7b2929961f'

def main():
    if sha(R/'plan.json')!=PIN or (R/'launch.json').exists() or list(R.glob('episode-*/native.json')):
        raise ValueError('not untouched preparation')
    if read(R/'preflight.json')['plan_sha256']!=PIN:raise ValueError('preflight changed')
    receipt=dict(status='WITHDRAWN_BEFORE_SUBMISSION',job=None,gpu_seconds=0,plan_sha256=PIN,
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        reason='Historical donor16307 base native-selected valid0/4, substantial generation/debug and native acceptance failures. Not a useful primary quality scheduling test. Reviewed before new outcomes or GPU submission.',
        replacement='Independent v2 same16 scheduling assignments and4.5GPUh cap, local27B with predeclared first-block generator eligibility. No borrowed old-run budget.')
    # The old immutable submit implementation uses exclusive creation of this
    # file, so this receipt also prevents accidental submission from old code.
    write(R/'submit-intent.json',receipt);write(R/'withdrawn.json',receipt)
    print('V1_WITHDRAWN_BEFORE_SUBMISSION_GPU_SECONDS_0')

if __name__=='__main__':main()
