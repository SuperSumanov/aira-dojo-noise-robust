import datetime as dt
from pathlib import Path

import pytest
from phase1.scripts import session_0904_maturity_intake_once_20260906 as wrapper


def test_separate_one_shot_inside_current_eight_hour_window():
    assert wrapper.START > wrapper.MATURITY
    assert wrapper.END-wrapper.START < 8*3600
    assert dt.datetime.fromtimestamp(wrapper.END, dt.timezone.utc).isoformat() == '2026-09-06T02:20:00+00:00'
    assert wrapper.BASELINE == '76a2d7d426b1da88f30d28449506fea78208f9ca5cd012ba6316efe346462285'
    assert wrapper.OUT.name == 'session-0904-maturity-intake-20260906'


@pytest.mark.parametrize('now', [wrapper.MATURITY, wrapper.START-1, wrapper.END, wrapper.END+1])
def test_early_or_expired_calls_do_not_open_files(monkeypatch, now):
    monkeypatch.setattr(wrapper.time, 'time', lambda: now)
    def forbidden(*a, **k): raise AssertionError('file_opened_outside_window')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    with pytest.raises(RuntimeError, match='outside_mature_session_window'): wrapper.main()


def test_unfinished_prior_output_refuses_reentry_before_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(wrapper.time, 'time', lambda: wrapper.START)
    monkeypatch.setattr(wrapper, 'OUT', tmp_path)
    (tmp_path/'poll-000').mkdir()
    def forbidden(*a, **k): raise AssertionError('file_opened_before_one_shot_check')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    with pytest.raises(RuntimeError, match='unfinished_prior_intake'): wrapper.main()


def test_call_limit_without_payload_read(monkeypatch, tmp_path):
    monkeypatch.setattr(wrapper.time, 'time', lambda: wrapper.START)
    monkeypatch.setattr(wrapper, 'OUT', tmp_path)
    for i in range(wrapper.MAX_CALLS): (tmp_path/f'wrapper-{i:03d}.json').touch()
    with pytest.raises(RuntimeError, match='session_call_limit'): wrapper.main()
