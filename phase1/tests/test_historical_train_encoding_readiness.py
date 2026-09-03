import hashlib
import json

import pytest

from phase1.historical_train_encoding_readiness import (
    EXPECTED, checked_digest, extract_train_inputs, independent_encode, train_rows,
)


class CharTokenizer:
    def __call__(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return {'input_ids': [ord(c) for c in text]}


@pytest.mark.parametrize('length', [0, 1, 7, 16, 100])
def test_reference_head_tail_and_task(length):
    text = '# MLE-bench task: t\n' + 'z' * length
    ids, raw = independent_encode('z' * length, 't', CharTokenizer(), max_len=32)
    expected = list(map(ord, text))
    if len(expected) > 32:
        expected = expected[:8] + expected[-24:]
    assert list(ids) == expected
    assert raw == len(text)


@pytest.mark.parametrize('max_len,head_frac', [(0,.25), (1,.25), (8,0), (8,1), (True,.25)])
def test_bad_truncation_rejected(max_len, head_frac):
    with pytest.raises(ValueError):
        independent_encode('code','task',CharTokenizer(),max_len=max_len,head_frac=head_frac)


def write_rows(tmp_path, rows):
    p = tmp_path / 'train.jsonl'
    p.write_text(''.join(json.dumps(x) + '\n' for x in rows))
    return p


def test_training_rows_only(tmp_path):
    x = {'better':'a','worse':'b','intask_split':'train','budget':0,'gap_raw':object.__name__}
    assert train_rows(write_rows(tmp_path,[x])) == [('a','b',0)]
    assert len(train_rows(write_rows(tmp_path,[x,dict(x,budget=1)]))) == 2
    for bad in [dict(x,intask_split='test'),dict(x,worse='a'),dict(x,budget=True)]:
        with pytest.raises(ValueError):
            train_rows(write_rows(tmp_path,[bad]))
    with pytest.raises(ValueError,match='duplicate'):
        train_rows(write_rows(tmp_path,[x,dict(x,better='b',worse='a')]))


def test_only_train_fields_retained_and_identity_unique():
    x={'r':[{'id':'a','code':'c','task':{'name':'t'},'grade':'must_not_read'},
            {'id':'non_train','no_code_or_task_required':True}]}
    code,tasks,runs,n=extract_train_inputs(x,{'a'})
    assert (code,tasks,runs,n)==({'a':'c'},{'a':'t'},{'a':'r'},2)
    with pytest.raises(ValueError,match='missing'):
        extract_train_inputs(x,{'missing'})
    with pytest.raises(ValueError,match='duplicate'):
        extract_train_inputs({'r':[x['r'][0],x['r'][0]]},{'a'})


def test_hash_and_credential_fail_closed(tmp_path):
    p=tmp_path/'data.txt'; p.write_bytes(b'clean')
    assert checked_digest(p,hashlib.sha256(b'clean').hexdigest(),True)
    with pytest.raises(ValueError,match='hash'):
        checked_digest(p,'0'*64)
    # Construct dummy credential shape at runtime; never a usable credential.
    p.write_bytes(b'sk-' + b'A'*24)
    with pytest.raises(ValueError,match='credential'):
        checked_digest(p,scan=True)


def test_immutable_hashes_well_formed():
    assert len(EXPECTED)==9
    assert all(len(x)==64 and int(x,16)>=0 for x in EXPECTED.values())
