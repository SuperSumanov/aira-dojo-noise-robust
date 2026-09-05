import os
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_runtime_prefix_opens_20260906 import decode_path_literal

@pytest.mark.parametrize('raw',[b'/tmp/a', '/old/任务/example.tar.gz'.encode(), b'/tmp/quote"backslash\\file', b'/tmp/byte\xff'])
def test_c_byte_roundtrip(raw):
    quoted='"'+''.join(chr(b) if 32<=b<127 and b not in (34,92) else '\\%03o'%b for b in raw)+'"'
    assert decode_path_literal(quoted).encode('utf-8',errors='surrogateescape')==raw

def test_rejects_ambiguous_unicode_literal():
    with pytest.raises(AssertionError):decode_path_literal('"/tmp/任务"')
