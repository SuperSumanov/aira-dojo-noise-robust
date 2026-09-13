"""Operational monitor of an explicitly supplied prepared width-control root."""
from pathlib import Path
import sys
import monitor_forets_branching_20260913 as monitor
if __name__=='__main__':
    root=Path(sys.argv[1]).resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):raise ValueError('scope')
    prepared=monitor.read(root/'prepared.json')
    if {r['arm'] for r in prepared['run_configs']}!={'batch_four','direct_two'}:raise ValueError('width package required')
    monitor.ROOT=root;monitor.run()
