import io
from pathlib import Path
import tarfile

import pytest

from phase1.scripts.install_private_cuda128_20260906 import validated_members, merge_component


def member(name, kind=tarfile.REGTYPE, link=''):
    obj=tarfile.TarInfo(name);obj.type=kind;obj.linkname=link;obj.size=1 if kind==tarfile.REGTYPE else 0
    return obj


def test_valid_file_and_internal_relative_library_link():
    rows=[member('component',tarfile.DIRTYPE),member('component/lib',tarfile.DIRTYPE),
          member('component/lib/libx.so.1'),member('component/lib/libx.so',tarfile.SYMTYPE,'libx.so.1')]
    assert validated_members(rows,'component')==4*4096


@pytest.mark.parametrize('value',[
    member('/absolute'),member('component/../escape'),member('elsewhere/a'),
    member('component/a',tarfile.SYMTYPE,'../../escape'),member('component/a',tarfile.SYMTYPE,'/absolute'),
    member('component/a',tarfile.LNKTYPE,'component/b'),member('component/a',tarfile.FIFOTYPE),
    member('component/a\ncontrol'),member('component/back\\slash'),
])
def test_rejects_unsafe_archive_members(value):
    with pytest.raises(RuntimeError):validated_members([value],'component')


def test_rejects_duplicate_archive_path():
    with pytest.raises(RuntimeError,match='archive_member_path'):
        validated_members([member('component/a'),member('component/a')],'component')


def test_component_docs_preserved_and_identical_header_collision_allowed(tmp_path):
    out=tmp_path/'prefix';out.mkdir()
    for component in ('a','b'):
        src=tmp_path/component;src.mkdir();(src/'include').mkdir()
        (src/'LICENSE').write_text(component)
        (src/'include'/'x.h').write_text('identical')
        assert merge_component(src,out,component)==[]
    assert (out/'share/components/a/LICENSE').read_text()=='a'
    assert (out/'share/components/b/LICENSE').read_text()=='b'
    assert (out/'include/x.h').read_text()=='identical'


def test_nonidentical_collision_does_not_overwrite(tmp_path):
    out=tmp_path/'prefix';out.mkdir();(out/'include').mkdir();(out/'include/x.h').write_text('original')
    src=tmp_path/'src';src.mkdir();(src/'include').mkdir();(src/'include/x.h').write_text('different')
    with pytest.raises(RuntimeError,match='merge_nonidentical_collision'):
        merge_component(src,out,'component')
    assert (out/'include/x.h').read_text()=='original'
