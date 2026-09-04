from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tarfile

import pytest

from phase1 import validate_senior_source_provenance_manifest as v1
from phase1 import validate_senior_source_provenance_v2 as v2
from phase1.scripts.audit_historical_source_dates_20260904 import analyze
from phase1.tests.test_senior_source_provenance_manifest import make_archive, expected_row, write_jsonl


@pytest.fixture
def case(tmp_path):
    run = 'family_seed_7_id_abcd1234__2026-08-07'
    member = 'batch-a/family_seed_7_id_abcd1234/checkpoint/journal.jsonl'
    source = tmp_path/'sources'
    archive = source/'0808/task-a.tar.gz'
    digest = make_archive(archive, [('batch-a', 'family_seed_7_id_abcd1234')])
    expected = tmp_path/'runs.jsonl'
    expected_sha = write_jsonl(expected, [expected_row(run)])
    row = dict(run_id=run, task='task-a', archive_path='0808/task-a.tar.gz', archive_sha256=digest,
               batch_id='batch-a', journal_member=member, producer_commit='d'*40,
               producer_instance_id='test-instance-0001', launch_date='2026-08-07', source_date='2026-08-08')
    return expected, expected_sha, source, row


def execute(case, tmp_path, rows=None):
    expected, expected_sha, root, row = case
    declaration = tmp_path/'declaration.jsonl'
    digest = write_jsonl(declaration, rows if rows is not None else [row])
    return v2.validate(expected, expected_sha, declaration, digest, root)


def test_cross_date_succeeds_without_resolving_old_identity_gate(case, tmp_path):
    a, b = execute(case,tmp_path), execute(case,tmp_path)
    assert a == b
    assert a['inventory']['launch_collection_date_differences'] == 1
    assert a['status'] == 'HEADER_BACKED_DECLARATION_ONLY_NOT_EFFECT_ELIGIBLE'
    assert not any(a['scope'].values())
    assert all(a['not_verified'].values())
    assert a['archives'][0]['referenced_journals'] == 1


def test_legacy_rejection_reproduced_and_not_modified(case, tmp_path):
    expected, expected_sha, root, row = case
    path = tmp_path/'legacy.jsonl'
    digest = write_jsonl(path,[{k:v for k,v in row.items() if k in v1.PROVENANCE_FIELDS}])
    with pytest.raises(v1.ContractError, match='source_date does not match'):
        v1.validate(expected,expected_sha,path,digest,root)


def test_same_date_also_supported(case, tmp_path):
    expected, _, root, row = case
    row['run_id'] = row['run_id'].replace('2026-08-07','2026-08-08')
    row['launch_date'] = '2026-08-08'
    sha = write_jsonl(expected,[expected_row(row['run_id'])])
    assert execute((expected,sha,root,row),tmp_path)['inventory']['launch_collection_date_differences'] == 0


@pytest.mark.parametrize('key,value,error', [
    ('launch_date','2026-08-08','launch_date_mismatch'),
    ('source_date','2026-08-09','collection_directory_date_mismatch'),
    ('source_date','2026-02-30','invalid_calendar_date'),
    ('source_date','20260808','noncanonical_calendar_date'),
    ('task','invented-task','task_mismatch'),
    ('archive_sha256','f'*64,'archive_digest_mismatch'),
    ('archive_path','0808/../task-a.tar.gz','traversal-free'),
    ('archive_path','0808/missing.tar.gz','archive is absent'),
    ('journal_member','other-batch/family_seed_7_id_abcd1234/checkpoint/journal.jsonl','journal_path_not_exactly_bound'),
    ('journal_member','batch-a/invented_seed_7_id_abcd1234/checkpoint/journal.jsonl','journal_path_not_exactly_bound'),
    ('journal_member','batch-a/nested/family_seed_7_id_abcd1234/checkpoint/journal.jsonl','journal_header_missing_or_duplicated'),
    ('producer_commit','d'*39,'invalid_declared_commit'),
    ('producer_instance_id','../instance','invalid_or_reused_instance'),
])
def test_contract_rejections(case,tmp_path,key,value,error):
    case[3][key] = value
    with pytest.raises(v2.ContractError, match=error):
        execute(case,tmp_path)


def test_missing_new_fields_not_inferred(case,tmp_path):
    del case[3]['launch_date']
    with pytest.raises(v2.ContractError,match='schema'):
        execute(case,tmp_path)


def test_extra_outcome_field_rejected(case,tmp_path):
    case[3]['grade'] = 1
    with pytest.raises(v2.ContractError,match='schema'):
        execute(case,tmp_path)


def test_coverage_and_reused_origin(case,tmp_path):
    expected,_,root,row=case
    new_run=row['run_id'].replace('2026-08-07','2026-08-06')
    expected_sha=write_jsonl(expected,[expected_row(row['run_id']),expected_row(new_run)])
    case=(expected,expected_sha,root,row)
    with pytest.raises(v2.ContractError,match='coverage_incomplete'):
        execute(case,tmp_path)
    second=dict(row,run_id=new_run,launch_date='2026-08-06')
    rows=sorted([row,second],key=lambda r:r['run_id'])
    with pytest.raises(v2.ContractError,match='reused_instance'):
        execute(case,tmp_path,rows)
    second['producer_instance_id']='test-instance-0002'
    with pytest.raises(v2.ContractError,match='journal_reused'):
        execute(case,tmp_path,rows)


def test_duplicate_run_id(case,tmp_path):
    with pytest.raises(v2.ContractError,match='unexpected_or_duplicate_run'):
        execute(case,tmp_path,[case[3],case[3]])


def test_duplicate_journal_or_link_rejected(case,tmp_path):
    _,_,root,row=case
    entry=('batch-a','family_seed_7_id_abcd1234')
    row['archive_sha256']=make_archive(root/row['archive_path'],[entry,entry])
    with pytest.raises(v2.ContractError,match='journal_header_missing_or_duplicated'):
        execute(case,tmp_path)
    row['archive_sha256']=make_archive(root/row['archive_path'],[entry],unsafe_link=True)
    with pytest.raises(v2.ContractError,match='unsupported_archive_member_type'):
        execute(case,tmp_path)


def test_payload_and_extraction_apis_never_called(case,tmp_path,monkeypatch):
    def deny(*args,**kwargs):
        raise AssertionError('payload/extraction API called')
    for method in ('extractfile','extract','extractall'):
        monkeypatch.setattr(tarfile.TarFile,method,deny)
    assert execute(case,tmp_path)['scope']['tar_member_payloads_opened'] is False


def test_duplicate_json_keys_rejected(case,tmp_path):
    expected,expected_sha,root,row=case
    raw=json.dumps(row)[:-1]+',"task":"task-a"}\n'
    p=tmp_path/'duplicate.jsonl'; p.write_text(raw,encoding='utf-8')
    with pytest.raises(v2.ContractError,match='duplicate_json_key'):
        v2.validate(expected,expected_sha,p,hashlib.sha256(p.read_bytes()).hexdigest(),root)


def test_archive_digest_changes_between_scans(case,tmp_path,monkeypatch):
    original=v1.sha256_file; calls=0
    def drift(path):
        nonlocal calls
        if Path(path).name.endswith('.tar.gz'):
            calls += 1
            if calls == 2:
                return '0'*64
        return original(path)
    monkeypatch.setattr(v1,'sha256_file',drift)
    with pytest.raises(v2.ContractError,match='archive_post_digest_mismatch'):
        execute(case,tmp_path)


def test_credential_and_symlink_checks_before_json(case,tmp_path):
    p=tmp_path/'unsafe.jsonl'
    raw=('s'+'k'+'-'+'X'*32).encode()
    p.write_bytes(raw)
    with pytest.raises(v2.ContractError,match='credential_shaped'):
        v2.read_metadata(p,hashlib.sha256(raw).hexdigest(),v2.FIELDS)
    symlink=tmp_path/'link.jsonl'
    try:
        symlink.symlink_to(p)
    except OSError:
        pytest.skip('host does not permit creating symlinks')
    with pytest.raises(v2.ContractError,match='symlinked_input'):
        v2.regular_unlinked(symlink)


def test_date_diagnostic_preserves_missing_and_ambiguous():
    def row(day,state,n,source):
        return dict(run_id=f'family_seed_{day}_id_abcd__2026-08-{day:02}',task='task',original_hold=False,
                    source_match_status=state,source_candidate_batches=n,source_day=source,
                    batch_sha256='a'*64 if state=='unique' else None)
    rows=[row(7,'unique',1,'0808'),row(8,'unique',1,'0808'),row(9,'ambiguous',2,None),row(10,'missing',0,None)]
    r=analyze(rows)
    assert analyze(list(reversed(rows)))==r
    assert r['unique_cross_date']==1 and r['unique_same_date']==1
    assert r['run_source_status']=={'unique':2,'ambiguous':1,'missing':1}
    assert r['ambiguous_sources_resolved']==r['missing_sources_resolved']==0
