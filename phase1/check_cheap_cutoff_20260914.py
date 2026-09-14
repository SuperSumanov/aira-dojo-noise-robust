"""Reuse the tested actual cutoff hook with only the fixed matrix count changed."""
import inspect,sys
from pathlib import Path
import verify_forets_wallclock_20260912 as parent
from forets_paid_patch_20260911 import once
source=once(inspect.getsource(parent.run),'len(configs)!=8','len(configs)!=12')
source=source.replace('actual_typed_configs=8','actual_typed_configs=12')
space=dict(vars(parent));exec(compile(source,'<12-config cutoff integration>','exec'),space)
if __name__=='__main__':space['run'](Path(sys.argv[1]),blocks=(1,2))
