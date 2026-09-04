"""One exact post-session intake after the fixed 0903 six-hour maturity gate."""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
import sys

from phase1.scripts import foreground_intake_session_20260905 as base


BASE_SHA256 = "d0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43"
DERIVED_SHELL_SHA256 = "f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599"
MATURITY = dt.datetime.fromisoformat("2026-09-05T00:09:48.832417+00:00").timestamp()
START = dt.datetime.fromisoformat("2026-09-05T00:10:00+00:00").timestamp()
END = dt.datetime.fromisoformat("2026-09-05T00:40:00+00:00").timestamp()
OUT = Path("/research/d7/spc/yzyang4/post-session-maturity-intake-20260905")
BASELINE = "bc9833d834fba65adbbf174301fe968c2c12da4eb8190a8f418ece58d0219456"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not (START > MATURITY and START >= base.END):
        raise RuntimeError("invalid_successor_window")
    if digest(Path(base.__file__)) != BASE_SHA256:
        raise RuntimeError("base_driver_drift")
    derived = Path(base.__file__).resolve().with_name(Path(base.REL).name)
    if digest(derived) != DERIVED_SHELL_SHA256:
        raise RuntimeError("derived_shell_drift")
    base.START = START
    base.END = END
    base.OUT = OUT
    base.BASELINE = BASELINE
    base.main()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) else "detail_withheld"
        print(f'{{"status":"POST_SESSION_MATURITY_INTAKE_FAILED_CLOSED","reason":"{reason}"}}')
        sys.exit(1)
