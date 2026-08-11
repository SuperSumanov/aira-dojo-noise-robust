"""Rebuild the fidelity manifest without the three tasks whose data does not exist locally.

aptos, dog-breed and histopathologic have no directory under mle-bench-data -- the senior's
runs executed against his own data tree -- so their children cannot be re-run here and would
burn cap-time on guaranteed mount failures. They are EXCLUDED and the exclusion is part of
the experiment's coverage statement (19 of 22 tasks; the three excluded are all image
tasks, which also bounds what the curve can claim about image workloads).

Kuzushiji stays: its public tar existed and is extracted by the time the full run starts.
Replacement sets are drawn from the same strata so the 100-set budget is kept.
"""
import json, subprocess, sys

MISSING = {"aptos2019-blindness-detection", "dog-breed-identification",
           "histopathologic-cancer-detection"}

# regenerate from scratch with the exclusion applied inside the same sampler
src = open("phase1/fidelity_manifest.py").read()
assert "MISSING_TASKS" not in src
src = src.replace(
    'sets_ = {par: ch for par, ch in sets_.items() if len(ch) >= 2}',
    '''MISSING_TASKS = %r   # no local data; excluded from the rerun universe
sets_ = {par: ch for par, ch in sets_.items()
         if len(ch) >= 2 and TASK[ch[0]] not in MISSING_TASKS}''' % MISSING)
open("phase1/fidelity_manifest.py", "w").write(src)
print("patched sampler; regenerating")
r = subprocess.run([sys.executable, "phase1/fidelity_manifest.py"],
                   capture_output=True, text=True)
print(r.stdout[-1200:])
if r.returncode:
    print(r.stderr[-500:])
    sys.exit(1)
