"""Both prepared blocks, no API/GPU execution."""
from pathlib import Path
import sys
from verify_forets_wallclock_20260912 import run
if __name__=='__main__':run(Path(sys.argv[1]),blocks=(1,2))
