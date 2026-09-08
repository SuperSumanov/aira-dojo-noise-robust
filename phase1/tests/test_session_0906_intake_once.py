from pathlib import Path
import pytest
from phase1.scripts import session_0906_intake_once_20260908 as m


def test_bounded_source_and_lease():
    assert m.END - m.START == 7200
    assert m.CALL_CAP == 2700 and m.MAX_CALLS == 8
    assert m.SOURCE.name == '0906' and m.OUT.name == 'session-0906-intake-20260908'
    assert m.BASELINE == '6db37288ac0fe2ca1b833ff63c3b10318cd13610c023a9d2412c194a67dfd116'


@pytest.mark.parametrize('now', [m.START - 1, m.END, m.END - m.CALL_CAP + 1])
def test_outside_window_does_not_open(monkeypatch, now):
    monkeypatch.setattr(m.time, 'time', lambda: now)
    def denied(*a, **k):
        raise AssertionError('opened')
    monkeypatch.setattr(Path, 'open', denied)
    with pytest.raises(RuntimeError, match='outside_bounded'):
        m.main()


def test_incomplete_prior_before_source(monkeypatch, tmp_path):
    monkeypatch.setattr(m.time, 'time', lambda: m.START)
    monkeypatch.setattr(m, 'OUT', tmp_path)
    (tmp_path / 'poll-000').mkdir()
    def denied(*a, **k):
        raise AssertionError('source read')
    monkeypatch.setattr(m, 'sha', denied)
    with pytest.raises(RuntimeError, match='unfinished'):
        m.main()


def test_limit_before_source(monkeypatch, tmp_path):
    monkeypatch.setattr(m.time, 'time', lambda: m.START)
    monkeypatch.setattr(m, 'OUT', tmp_path)
    for i in range(m.MAX_CALLS):
        (tmp_path / f'wrapper-{i:03d}.json').touch()
    with pytest.raises(RuntimeError, match='call_limit'):
        m.main()


def test_restore_globals_after_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(m.time, 'time', lambda: m.START)
    monkeypatch.setattr(m, 'OUT', tmp_path)
    monkeypatch.setattr(m, 'sha', lambda p: m.BASE_SHA if p.name.endswith('.py') else m.SHELL_SHA)
    monkeypatch.setattr(m, 'source_binding', lambda: 'fixed')
    before = (m.base.START, m.base.END, m.base.OUT, m.base.BASELINE)
    def fail():
        raise RuntimeError('original_failed')
    monkeypatch.setattr(m.base, 'main', fail)
    with pytest.raises(RuntimeError, match='original_failed'):
        m.main()
    assert (m.base.START, m.base.END, m.base.OUT, m.base.BASELINE) == before


def test_drift_after_intake_has_no_success_wrapper(monkeypatch, tmp_path):
    monkeypatch.setattr(m.time, 'time', lambda: m.START)
    monkeypatch.setattr(m, 'OUT', tmp_path)
    monkeypatch.setattr(m, 'sha', lambda p: m.BASE_SHA if p.name.endswith('.py') else m.SHELL_SHA)
    bindings = iter(['before', 'after'])
    monkeypatch.setattr(m, 'source_binding', lambda: next(bindings))
    monkeypatch.setattr(m.base, 'main', lambda: None)
    with pytest.raises(RuntimeError, match='source_changed_during_intake'):
        m.main()
    assert not list(tmp_path.glob('wrapper-*'))
