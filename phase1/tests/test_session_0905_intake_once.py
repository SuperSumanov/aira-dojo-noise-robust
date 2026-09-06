from pathlib import Path
import pytest
from phase1.scripts import session_0905_intake_once_20260907 as m


def test_fixed_lease_and_unchanged_baseline():
    assert 0<m.END-m.START<6*3600
    assert m.CALL_CAP==2700 and m.MAX_CALLS==16
    assert m.BASELINE=='cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2'
    assert m.OUT.name=='session-0905-intake-20260907'


@pytest.mark.parametrize('now',[m.START-1,m.END,m.END-m.CALL_CAP+1])
def test_no_file_open_outside_full_call_window(monkeypatch,now):
    monkeypatch.setattr(m.time,'time',lambda:now)
    def forbidden(*a,**k):raise AssertionError('opened')
    monkeypatch.setattr(Path,'open',forbidden)
    with pytest.raises(RuntimeError,match='outside_bounded'):m.main()


def test_incomplete_prior_call_stops_before_source_read(monkeypatch,tmp_path):
    monkeypatch.setattr(m.time,'time',lambda:m.START);monkeypatch.setattr(m,'OUT',tmp_path)
    (tmp_path/'poll-000').mkdir()
    def forbidden(*a,**k):raise AssertionError('read before incomplete gate')
    monkeypatch.setattr(m,'sha',forbidden)
    with pytest.raises(RuntimeError,match='unfinished'):m.main()


def test_call_limit_before_source_read(monkeypatch,tmp_path):
    monkeypatch.setattr(m.time,'time',lambda:m.START);monkeypatch.setattr(m,'OUT',tmp_path)
    for i in range(m.MAX_CALLS):(tmp_path/f'wrapper-{i:03d}.json').touch()
    with pytest.raises(RuntimeError,match='call_limit'):m.main()


def test_base_globals_restore_when_original_intake_fails(monkeypatch,tmp_path):
    monkeypatch.setattr(m.time,'time',lambda:m.START);monkeypatch.setattr(m,'OUT',tmp_path)
    monkeypatch.setattr(m,'sha',lambda p:m.BASE_SHA if p.name.endswith('.py') else m.SHELL_SHA)
    monkeypatch.setattr(m,'source_binding',lambda:None)
    before=(m.base.START,m.base.END,m.base.OUT,m.base.BASELINE)
    def failed():raise RuntimeError('original_failed')
    monkeypatch.setattr(m.base,'main',failed)
    with pytest.raises(RuntimeError,match='original_failed'):m.main()
    assert (m.base.START,m.base.END,m.base.OUT,m.base.BASELINE)==before
