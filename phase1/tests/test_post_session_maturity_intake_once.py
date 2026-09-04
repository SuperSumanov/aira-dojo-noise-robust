import datetime as dt

from phase1.scripts import foreground_intake_session_20260905 as base
from phase1.scripts import post_session_maturity_intake_once_20260905 as successor


def test_successor_starts_after_both_gates():
    assert successor.START > successor.MATURITY
    assert successor.START >= base.END
    assert successor.END > successor.START


def test_successor_is_one_shot_distinct_root():
    assert successor.OUT != base.OUT
    assert successor.BASELINE == base.BASELINE
    assert dt.datetime.fromtimestamp(successor.END, dt.timezone.utc).isoformat() == "2026-09-05T00:40:00+00:00"
