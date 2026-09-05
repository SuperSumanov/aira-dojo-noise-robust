import io
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_historical_source_ledger import components, config_stratum, origin_index, stream_fingerprint
from recover_historical_production_configs import RecoveryError


def test_stratum_only_omits_instance_output_paths():
    cfg={'metadata':{'git_commit_id':'a'*40},'solver':{'exp_name':'a','checkpoint_path':'/a','time_limit_secs':10},
         'task':{'name':'task','results_output_dir':'/a'},'interpreter':{'working_dir':'/a','timeout':10}}
    original=config_stratum(cfg)
    cfg['interpreter']['working_dir']='/b';cfg['solver']['exp_name']='b';cfg['task']['results_output_dir']='/b'
    assert config_stratum(cfg)==original
    cfg['interpreter']['timeout']=11
    assert config_stratum(cfg)!=original


def test_component_closes_shared_archives_and_shared_meta():
    def row(archive,meta):return {'archive_sha256':archive,'config_member':'batch/run/dojo_config.json','recorded_meta_id':meta}
    groups=components({'a':[row('x','1')],'b':[row('x','2')],'c':[row('y','2')],'d':[row('z','4')]})
    assert groups==[['a','b','c'],['d']]


def test_hashes_opaque_non_json():
    assert len(stream_fingerprint(io.BytesIO(b'not JSON'),8,time.monotonic()+10))==64


def test_credential_across_chunk_boundary():
    data=b'x'*(1024**2-4)+b' sk-'+b'z'*32
    with pytest.raises(RecoveryError):stream_fingerprint(io.BytesIO(data),len(data),time.monotonic()+10)


def test_truncation_refused():
    with pytest.raises(RecoveryError):stream_fingerprint(io.BytesIO(b'ab'),3,time.monotonic()+10)


def test_exact_archive_member_copies_are_not_new_origins():
    row={'archive_sha256':'a','config_member':'b/run/dojo_config.json','config_sha256':'c'}
    assert origin_index({'run':[row,row]})=={'a':{'b/run/dojo_config.json':('run','c')}}
    with pytest.raises(RecoveryError):origin_index({'run':[row],'different_run':[row]})
    with pytest.raises(RecoveryError):origin_index({'run':[row,dict(row,config_sha256='changed')]})
