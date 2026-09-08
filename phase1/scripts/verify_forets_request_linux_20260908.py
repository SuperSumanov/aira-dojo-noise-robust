"""Independent, read-only structural verification of the fixed CPU test directory."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path('/research/d7/spc/yzyang4/forets-request-20260908-lfC8VhL1')
EXPECTED = {
    "phase1/forets_batch_runtime_20260908.py": "3879cf22243076b28c04098bcfc49f9cc01b5e68fa2e346f8b227873c1c1b91e",
    "phase1/forets_candidate_ledger_20260908.py": "83a75a47feab3953d1cd8a31a4ed1e0af3685a497dbea73eb1f00fb3eb09e4ae",
    "phase1/forets_linux_validation_20260908.py": "f2419243eaaaede19a7768c616046f9cef79ecb36bf45cc752ac016357698daf",
    "phase1/forets_request_guard_20260908.py": "0197d6fdb61ff001341cec9eaf62dff0a9c31e288b41aced1a1a5c4d913abf5d",
    "phase1/forets_request_linux_validation_20260908.py": "fe8038e49a96e300bbf55cc6820df72e5a25673e4f9651ad154fbe21691672bd",
    "phase1/forets_request_patch_20260908.py": "2708cba8de5a434747cba1927512e33092e3e4cdc0b68d6aa3d1dc13da602ffb",
    "phase1/forets_state_patch_20260908.py": "dbda7c87be2e2ce86827d1cdf36ef2eda32a89f781f1407a5bf96fdf7cfb502b",
    "phase1/forets_upstream_hotfix_20260908.py": "277254d1d89ac83738cc94b459a8bbb8b32780396da40cfd85fdbcc1d4964609",
    "phase1/tests/test_forets_candidate_state_20260908.py": "195d52026764fe3d8f4c3169ace60f1a05dab986ce2a3891e5986a7971a76055",
    "phase1/tests/test_forets_request_boundary_20260908.py": "e2a2bd1365e527a7b847fca80d2d1678c7ce62b1958d5880cf53d6a344423acf",
    "phase1/tests/test_forets_upstream_hotfix_20260908.py": "12a6e3b98b18455661ad77b4c28554eba5d5bd3371f679ae6978775db66c34fe",
    "codex_tmp/forets-request-20260908/source_cache.json": "7a85be5a6accc0b4022af6c59a35a331dce5a92fefff05d7880e1b6fc40a9be7"
}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert ROOT.resolve() == ROOT
receipt_path = ROOT / 'validation_receipt.json'
assert receipt_path.stat().st_size < 65536
receipt = json.loads(receipt_path.read_bytes())
assert receipt['source_commit'] == '486ff8f7afdf6b35b9d2175b9b87328d3aced01f'
assert receipt['archive_sha256'] == '86fd6bb67c6d108058482a490a410cb242eb2f9a1d175c8810e3ed05b4369225'
assert sha(ROOT / 'payload.tar') == '86fd6bb67c6d108058482a490a410cb242eb2f9a1d175c8810e3ed05b4369225'
assert receipt['exit_code'] == 0 and receipt['unchanged_inputs'] is True
assert receipt['file_sha256'] == EXPECTED
assert {p:sha(ROOT / p) for p in EXPECTED} == EXPECTED
xml_path = ROOT / 'linux_tests.xml'
assert xml_path.stat().st_size < 1048576
tree = ET.fromstring(xml_path.read_bytes())
suites = list(tree.iter('testsuite'))
cases = list(tree.iter('testcase'))
assert len(suites) == 1 and int(suites[0].attrib['tests']) == 69 and len(cases) == 69
assert all(int(suites[0].attrib[k]) == 0 for k in ('errors','failures','skipped'))
assert len({(c.attrib['classname'],c.attrib['name']) for c in cases}) == 69
assert not list(tree.iter('failure')) and not list(tree.iter('error'))
assert (ROOT / 'test_stderr.txt').stat().st_size == 0
assert not list(ROOT.rglob('*.lock'))
out = dict(classification='INDEPENDENT_REQUEST_BOUNDARY_VERIFICATION_NOT_MODEL_EFFECT',
           source_commit=receipt['source_commit'], tests=69, failures=0, errors=0, skipped=0,
           exact_payload_files=len(EXPECTED), receipt_sha256=sha(receipt_path),
           xml_sha256=sha(xml_path), archive_sha256=receipt['archive_sha256'],
           source_cache_sha256=EXPECTED['codex_tmp/forets-request-20260908/source_cache.json'],
           heldout_inputs_opened=False, gpu_jobs=0, model_fits=0, production_ready=False)
print(json.dumps(out, sort_keys=True))
