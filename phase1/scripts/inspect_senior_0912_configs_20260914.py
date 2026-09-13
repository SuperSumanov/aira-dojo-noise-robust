"""Credential-first config metadata only; no journals/outcomes/env/code opened."""
from pathlib import Path
import inspect_senior_quarantine_20260911 as inspector
inspector.ROOT=Path('/research/d7/spc/yzyang4/senior-quarantine-0912-20260914')
inspector.MANIFEST_SHA='d7297d76a39a1e141ff2b63f1f22c45148b9d5b8075fede8da0716b13ea7822c'
inspector.ARCHIVE_COUNT=1
if __name__=='__main__':
    try:inspector.main()
    except Exception as e:
        import json
        print(json.dumps(dict(status='CONFIG_METADATA_FAILED_CLOSED',error_type=type(e).__name__)))
        raise SystemExit(2)
