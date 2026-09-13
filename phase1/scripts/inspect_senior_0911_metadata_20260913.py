"""Only credential-screened config metadata from the one new quarantined archive."""
from pathlib import Path
import inspect_senior_quarantine_20260911 as inspector
inspector.ROOT=Path('/research/d7/spc/yzyang4/senior-quarantine-0911-20260913')
inspector.MANIFEST_SHA='c1ee6108efc3bdb08cb5ffd676df141573629cd81011f8cbe68ab56cbd0411e1'
inspector.ARCHIVE_COUNT=1
if __name__=='__main__':
    try:inspector.main()
    except Exception as exc:
        import json
        print(json.dumps(dict(status='CONFIG_METADATA_FAILED_CLOSED',error_type=type(exc).__name__)))
        raise SystemExit(2)
