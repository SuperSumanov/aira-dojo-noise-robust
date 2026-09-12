"""Export the actual running seed15 code/config, never programs or outcomes."""
from pathlib import Path
import export_forets_context_capsule_20260912 as export


if __name__=='__main__':
    export.ROOT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-3no2iopd')
    export.TREE='54e353963a6899965896b2e8ea492207829b3cbd'
    export.LAUNCHER='launchers/forets_repeat_20260912.sbatch'
    export.CAPSULE_NAME='release-code-capsule-s15-v1'
    export.main()
