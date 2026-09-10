import json
import hashlib
import datetime

import pytest

from phase1 import forets_stage_gate as gate


def tasks(states):
    return {str(i): {'status': status} for i, status in enumerate(states)}


@pytest.mark.parametrize('first_two', [('completed','completed'),('failed','failed'),('failed','completed')])
def test_first_pair_stops_regardless_of_success(first_two):
    assert gate.stage_reached(tasks(list(first_two)+['pending']*6), 2)


def test_does_not_cancel_second_run_or_skip_pair_member():
    assert not gate.stage_reached(tasks(['completed','running']+['pending']*6), 2)
    assert not gate.stage_reached(tasks(['failed','pending']+['pending']*6), 2)
    assert not gate.stage_reached(tasks(['completed']*2+['pending']*6), 8)


@pytest.mark.parametrize('limit', [0,1,3,True])
def test_no_single_arm_or_arbitrary_stage(limit):
    with pytest.raises(ValueError):
        gate.stage_reached(tasks(['pending']*8), limit)


def test_compatibility_reuse_refuses_changed_node_image_or_receipt(tmp_path, monkeypatch):
    image = tmp_path/'fixture.sif'
    image.write_bytes(b'public fixture')
    stat = image.stat()
    payloads = {
        'container.compatibility.json': dict(node='gpu28', image=str(image), image_bytes=stat.st_size,
            image_mtime_ns=stat.st_mtime_ns, forward_backward_cuda=True),
        'critic.ready.json': dict(deployment_check=dict(context=16384, all_parameters_cuda_bf16=True)),
    }
    hashes = {}
    for name, data in payloads.items():
        raw = json.dumps(data).encode()
        (tmp_path/name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(gate, 'RECEIPTS', hashes)
    assert gate.prior_compatibility('gpu28', image, tmp_path)['synthetic_gpu_forwards'] == 0
    with pytest.raises(RuntimeError): gate.prior_compatibility('gpu27', image, tmp_path)
    image.write_bytes(b'different fixture')
    with pytest.raises(RuntimeError): gate.prior_compatibility('gpu28', image, tmp_path)
    (tmp_path/'critic.ready.json').write_text('{}')
    with pytest.raises(RuntimeError): gate.prior_compatibility('gpu28', image, tmp_path)


def test_failed_live_receipt_rejected_before_source_access(tmp_path):
    receipt = tmp_path/'failed.json'
    receipt.write_text(json.dumps(dict(status='NOT_READY', calls=[{'fixture_matched':True},{'fixture_matched':False}])))
    with pytest.raises(RuntimeError, match='no successful'):
        gate.validate_route_receipt(receipt, tmp_path/'absent-source')


def test_ready_receipt_must_be_fresh_and_code_bound(tmp_path):
    source = tmp_path/'source'
    folder = source/'src/dojo/core/solvers/llm_helpers/backends'
    folder.mkdir(parents=True)
    for name in ('lite_llm.py','bounded_retry.py'):
        (folder/name).write_bytes(b'public-code-fixture')
    now = datetime.datetime.now(datetime.timezone.utc)
    data = dict(status='READY', calls=[dict(fixture_matched=True)]*2,
        public_artificial_input_only=True, model='nvidia/nemotron-3-ultra-550b-a55b:free',
        utc=now.isoformat(), source_hashes={name:hashlib.sha256(b'public-code-fixture').hexdigest()
            for name in ('lite_llm.py','bounded_retry.py')})
    receipt = tmp_path/'ready.json'
    receipt.write_text(json.dumps(data))
    assert gate.validate_route_receipt(receipt, source, now)['observed_utc'] == data['utc']
    with pytest.raises(RuntimeError, match='stale'):
        gate.validate_route_receipt(receipt, source, now+datetime.timedelta(hours=2))
    (folder/'lite_llm.py').write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='transport code'):
        gate.validate_route_receipt(receipt, source, now)
