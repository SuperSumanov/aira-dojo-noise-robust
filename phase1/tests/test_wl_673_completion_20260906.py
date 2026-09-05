import importlib.util
from pathlib import Path
import pytest

SOURCE = Path(__file__).parents[1] / 'scripts/verify_wl_673_completion_20260906.py'
spec = importlib.util.spec_from_file_location('wl_completion', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def receipt():
    return dict(snapshot_sha256=m.TARGET, artifact_summary_sha256='a' * 64,
                independent_verification_sha256='b' * 64, selected_runs=673,
                added_runs=156, removed_runs=0, common_pairs=3000,
                support_gate_is_provisional_until_closure=True, outcomes_read=False,
                effect_metrics_computed=[])


def test_exact_safe_receipt():
    m.validate_receipt(receipt())


@pytest.mark.parametrize('field,value', [
    ('selected_runs', 517), ('selected_runs', True), ('added_runs', '156'),
    ('removed_runs', 1), ('common_pairs', True), ('common_pairs', -1),
    ('outcomes_read', True), ('outcomes_read', 0),
    ('support_gate_is_provisional_until_closure', False), ('effect_metrics_computed', ['accuracy']),
    ('artifact_summary_sha256', 'x' * 64), ('snapshot_sha256', m.PRIOR),
])
def test_modified_receipt_refused(field, value):
    r = receipt()
    r[field] = value
    with pytest.raises(RuntimeError):
        m.validate_receipt(r)


def test_unknown_receipt_field_refused():
    r = receipt()
    r['unapproved'] = 'anything'
    with pytest.raises(RuntimeError, match='receipt_schema'):
        m.validate_receipt(r)


def test_valid_manifest_paths():
    raw = ('a' * 64 + '  ./one.json\n' + 'b' * 64 + '  ./sub/two.txt\n').encode()
    assert m.manifest_entries(raw) == {'one.json': 'a' * 64, 'sub/two.txt': 'b' * 64}


@pytest.mark.parametrize('name', ['../private', '/absolute', 'a/../b', 'a//b', 'a\\b', './a', 'x\x00y'])
def test_unsafe_manifest_refused(name):
    with pytest.raises(RuntimeError):
        m.manifest_entries(('a' * 64 + '  ./' + name + '\n').encode())


def test_duplicate_manifest_refused():
    with pytest.raises(RuntimeError, match='duplicate_manifest_path'):
        m.manifest_entries((('a' * 64 + '  ./same\n') * 2).encode())


def test_empty_manifest_refused():
    with pytest.raises(RuntimeError):
        m.manifest_entries(b'')


def test_no_numerical_payload_deserialization():
    text = SOURCE.read_text(encoding='utf-8')
    assert 'torch.load' not in text and 'np.load' not in text and 'numpy.load' not in text
    assert 'safe_json(FORMAL / \'artifact/summary.json\')' not in text
    assert "safe_json(FORMAL / 'independent_verification.json')" not in text
    assert "safe_json(FORMAL / 'snapshot_chain_receipt.json')" not in text
    assert 'sbatch' not in text and 'subprocess.Popen' not in text
