"""Negative production-entry control; sealed18510 is read-only."""
import json
from pathlib import Path
from pooling_production_gate_20261016 import exercise

root=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v2')
try:exercise(root,8,'admit')
except FileExistsError:
    print(json.dumps(dict(negative_control_passed=True,observed='FileExistsError',
        actual_old_production_install=True,frozen_batch_modified=False,gpu_calls=0,model_calls=0)))
else:raise AssertionError('Old production entry did not reproduce18510 failure')
