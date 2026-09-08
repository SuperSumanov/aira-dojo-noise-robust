"""Read-only independent verification; no test execution or protected data reads."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/forets-selection-20260908-YyGg83UH')
EXPECTED = {
    "phase1/forets_execution_patch_20260908.py": "981f5bff8bf49e80714dc22ad3836ab1090276fed4b3b727aa1694886898dae7",
    "phase1/forets_execution_witness_20260908.py": "7c046f8564f00ef6aa3d8fba0c3e96f6a60b1ee1a3cb795b10d3e5b277a4d310",
    "phase1/forets_selection_20260908.py": "6f5d1b3c4f02abc78a0cab652f4b3edc6f7dbf1419bf375a07760ea3172050e5",
    "phase1/forets_selection_linux_validation_20260908.py": "74d95c532f70ce4368349cf6903c365cc6b0b1b9e52e7b5f849d8cb68ab701fa",
    "phase1/forets_selection_patch_20260908.py": "fd2d3dd52c2042a5868af81e8863dcea22bbb2d4e592c60441f0164f10fafc57",
    "phase1/tests/test_forets_execution_witness_20260908.py": "97e103a12507b1d87a5f7dd587ac414059a6ec2f49b64b74f4e8586ebc4f86e4",
    "phase1/tests/test_forets_selection_20260908.py": "5aaf6e34ae4879bf7bfc9e73a93343cc3c6b8e3e7135c37f9a004aa25409bfac",
    "source_cache.json": "bd92cda8d5cacc9630dffddf18520bcd20de22e3a698096def73793776995b5b"
}


def main():
    assert ROOT.resolve() == ROOT
    receipt_bytes = (ROOT / 'validation_receipt.json').read_bytes()
    receipt = json.loads(receipt_bytes)
    assert receipt['source_commit'] == '82242e68e6d5f5584972ae7f892236d0454e64b1'
    assert receipt['exit_code'] == 0 and not receipt['timed_out'] and receipt['unchanged_inputs']
    assert receipt['file_sha256'] == EXPECTED
    for path, sha in EXPECTED.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    archive_sha = hashlib.sha256((ROOT / 'payload.tar').read_bytes()).hexdigest()
    assert archive_sha == receipt['archive_sha256'] == 'cc53a41c407d005f4b8239d145bee53705449fb564a5ffc2436d8a6446500e97'
    xml_bytes = (ROOT / 'linux_tests.xml').read_bytes()
    tree = ET.fromstring(xml_bytes)
    cases = tree.findall('.//testcase')
    identities = {(c.attrib['classname'], c.attrib['name']) for c in cases}
    assert len(cases) == len(identities) == 16
    assert not any(tree.findall('.//' + tag) for tag in ('failure', 'error', 'skipped'))
    assert any(name == 'test_real_batch_full_pool_critic_null_exactly_matches_random' for _,name in identities)
    summary_bytes = (ROOT / 'test_summary.json').read_bytes()
    summary = json.loads(summary_bytes)
    assert summary['exit_code'] == 0
    assert not list((ROOT / 'pytest-temp').rglob('*.sqlite.lock'))
    assert any(name == 'test_random_arm_never_queries_critic_and_preserves_unselected_unknown' for _,name in identities)
    assert summary['upstream'] == '54929de4ac92cb1a1a2fd75e31843a223c10c859'
    assert summary['source_tree'] == 'a999d8aaf8e9278e4e1eab57e5e45d2b0f87aa48'
    assert summary['source_cache_sha256'] == EXPECTED['source_cache.json']
    assert all(summary[k] == 0 for k in ('gpu_jobs', 'paid_api_calls', 'model_fits', 'production_programs_executed'))
    assert (ROOT / 'test_stderr.txt').read_bytes() == b''
    public_files = ('validation_receipt.json', 'linux_tests.xml', 'test_summary.json', 'test_stdout.txt')
    security = re.compile(rb'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')
    for name in public_files:
        assert not security.search((ROOT / name).read_bytes()), 'credential shape in export; stop'
    print(json.dumps(dict(verified=True, tests=16, unique_cases=16, failures=0, errors=0, skipped=0,
        source_commit=receipt['source_commit'], source_files_equal_git=7, unchanged_inputs=8,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        xml_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        summary_sha256=hashlib.sha256(summary_bytes).hexdigest(),
        synthetic_null_control_passed=True, zero_critic_baseline_passed=True, ledger_locks=0,
        production_ready=False), sort_keys=True))


if __name__ == '__main__':
    main()
