"""Read-only independent verification; no test execution or protected data reads."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/forets-execution-20260908-dw7WTqrL')
EXPECTED = {
    'phase1/forets_execution_witness_20260908.py': '7c046f8564f00ef6aa3d8fba0c3e96f6a60b1ee1a3cb795b10d3e5b277a4d310',
    'phase1/forets_execution_patch_20260908.py': '981f5bff8bf49e80714dc22ad3836ab1090276fed4b3b727aa1694886898dae7',
    'phase1/forets_execution_linux_validation_20260908.py': '85f91417506603071b6a05edff1002507d72a76b4ed5a0f85df9c4f11a3db627',
    'phase1/tests/test_forets_execution_witness_20260908.py': '97e103a12507b1d87a5f7dd587ac414059a6ec2f49b64b74f4e8586ebc4f86e4',
    'source_cache.json': 'a455b7ebe8a16f092f4b2a664a28025e988d46dcc8669194f2814188c284ff5d',
}


def main():
    assert ROOT.resolve() == ROOT
    receipt_bytes = (ROOT / 'validation_receipt.json').read_bytes()
    receipt = json.loads(receipt_bytes)
    assert receipt['source_commit'] == '28531549eb34fee78c4d198112688b250ab6cda4'
    assert receipt['exit_code'] == 0 and not receipt['timed_out'] and receipt['unchanged_inputs']
    assert receipt['file_sha256'] == EXPECTED
    for path, sha in EXPECTED.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    archive_sha = hashlib.sha256((ROOT / 'payload.tar').read_bytes()).hexdigest()
    assert archive_sha == receipt['archive_sha256'] == '6b1af042e2b946a0625eb840c44dbba0254b033fd6a5a4dee29fd393efa712cb'
    xml_bytes = (ROOT / 'linux_tests.xml').read_bytes()
    tree = ET.fromstring(xml_bytes)
    cases = tree.findall('.//testcase')
    identities = {(c.attrib['classname'], c.attrib['name']) for c in cases}
    assert len(cases) == len(identities) == 16
    assert not any(tree.findall('.//' + tag) for tag in ('failure', 'error', 'skipped'))
    assert any(name == 'test_real_python_interpreter_benign_process_through_task_witness' for _,name in identities)
    summary_bytes = (ROOT / 'test_summary.json').read_bytes()
    summary = json.loads(summary_bytes)
    assert summary['exit_code'] == 0 and summary['active_test_children'] == 0
    assert summary['upstream'] == '54929de4ac92cb1a1a2fd75e31843a223c10c859'
    assert summary['source_tree'] == '08d78ba2b0cf71c44cbd9eda34df15ae60049409'
    assert summary['source_cache_sha256'] == EXPECTED['source_cache.json']
    assert all(summary[k] == 0 for k in ('gpu_jobs', 'paid_api_calls', 'model_fits', 'production_programs_executed'))
    assert (ROOT / 'test_stderr.txt').read_bytes() == b''
    public_files = ('validation_receipt.json', 'linux_tests.xml', 'test_summary.json', 'test_stdout.txt')
    security = re.compile(rb'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')
    for name in public_files:
        assert not security.search((ROOT / name).read_bytes()), 'credential shape in export; stop'
    print(json.dumps(dict(verified=True, tests=16, unique_cases=16, failures=0, errors=0, skipped=0,
        source_commit=receipt['source_commit'], source_files_equal_git=4, unchanged_inputs=5,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        xml_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        summary_sha256=hashlib.sha256(summary_bytes).hexdigest(),
        real_benign_cpu_case_passed=True, active_test_children=0,
        production_ready=False), sort_keys=True))


if __name__ == '__main__':
    main()
