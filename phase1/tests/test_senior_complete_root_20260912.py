import importlib.util
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1]/'scripts/inspect_senior_complete_root_20260912.py'
spec = importlib.util.spec_from_file_location('complete_root', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def page(n):
    return '<title>artificial</title>' + ''.join(
        f'<a href="https://drive.google.com/drive/folders/{i:026d}">09{i:02d}</a>' for i in range(n))


def test_more_than_fifty_and_order_independent():
    items = module.embedded_items(page(61))
    assert len(items) == 61
    assert len(module.validate(items, list(reversed(items)), items[:50])) == 11


@pytest.mark.parametrize('html', ['<title>empty</title>', '<a href="https://elsewhere.invalid">x</a>',
    '<title>x</title><a href="https://drive.google.com.attacker.invalid/drive/folders/12345678901234567890123456">x</a>',
    page(1)+page(1)])
def test_bad_or_duplicate_listing(html):
    with pytest.raises(ValueError):
        module.embedded_items(html)


def test_drift_and_missing_old_items():
    items = module.embedded_items(page(3))
    with pytest.raises(ValueError):
        module.validate(items, items[:-1], items[:1])
    with pytest.raises(ValueError):
        module.validate(items[:-1], items[:-1], items)
    with pytest.raises(ValueError):
        module.validate(items, items, [(items[0][0], 'renamed', module.FOLDER)])


def test_credential_shape_not_exported():
    html = '<title>x</title><a href="https://drive.google.com/drive/folders/12345678901234567890123456">' + 'sk-'+'a'*20+'</a>'
    with pytest.raises(ValueError):
        module.embedded_items(html)
