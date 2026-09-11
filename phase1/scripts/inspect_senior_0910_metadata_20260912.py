"""Only six 0910 quarantined archives; credential-screened config metadata.

No journals, env dumps, labels, candidate code, evaluation data or sidecar
contents are read; no production source or training admission is changed.
"""
from pathlib import Path
import inspect_senior_quarantine_20260911 as inspector

inspector.ROOT=Path('/research/d7/spc/yzyang4/senior-quarantine-0910-20260912')
inspector.MANIFEST_SHA='536251cce2d7aa0324f2e5b5ad638cbeced5e33b76166f2dc02f2e491b802c2c'
inspector.ARCHIVE_COUNT=6

if __name__=='__main__':
    try:inspector.main()
    except Exception as exc:
        import json
        print(json.dumps({'status':'CONFIG_METADATA_FAILED_CLOSED','error_type':type(exc).__name__}))
        raise SystemExit(1)
