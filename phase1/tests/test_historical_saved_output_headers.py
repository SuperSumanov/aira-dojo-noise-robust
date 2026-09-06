import io,tarfile
import pytest
from phase1.historical_saved_output_headers import category,scan,sha

def archive(tmp_path,members):
    path=tmp_path/'input.tar'
    with tarfile.open(path,'w') as tar:
        for n,data in members:
            info=tarfile.TarInfo(n);info.size=len(data);tar.addfile(info,io.BytesIO(data))
    return path

def test_scoped_headers_never_open_payload(tmp_path,monkeypatch):
    p=archive(tmp_path,[('batch/run/dojo_config.json',b'{}'),('batch/run/submission.csv',b'forbidden payload'),
                        ('batch/outside/submission.csv',b'outside scope')])
    monkeypatch.setattr(tarfile.TarFile,'extractfile',lambda *a:pytest.fail('member payload opened'))
    result=scan(p,sha(p),{'opaque':'batch/run'})
    assert result['runs']=={'opaque':{'submission_named_table':1}} and result['member_payloads_opened']==0

@pytest.mark.parametrize('name',['/outside','batch/run/../outside'])
def test_bad_headers_rejected(tmp_path,name):
    p=archive(tmp_path,[('batch/run/dojo_config.json',b'{}'),(name,b'x')])
    with pytest.raises(AssertionError,match='unsafe_header'):scan(p,sha(p),{'opaque':'batch/run'})

def test_archive_and_scope_guards(tmp_path):
    p=archive(tmp_path,[('batch/run/dojo_config.json',b'{}')])
    with pytest.raises(AssertionError,match='pre_hash'):scan(p,'0'*64,{'opaque':'batch/run'})
    with pytest.raises(AssertionError,match='missing_config'):scan(p,sha(p),{'opaque':'batch/missing'})
    with pytest.raises(AssertionError,match='nested'):scan(p,sha(p),{'a':'batch','b':'batch/run'})

def test_categories_are_only_hints():
    assert category('checkpoint/journal.jsonl') is None and category('env') is None
    assert category('sub/submission.csv')=='submission_named_table'
    assert category('sub/score.csv')=='other_table'
    assert category('sub/grading.json')=='possible_grading_record'
    assert category('uv.lock')=='dependency_manifest'
