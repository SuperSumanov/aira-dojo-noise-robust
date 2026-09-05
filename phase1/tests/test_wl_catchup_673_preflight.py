import ast
from pathlib import Path
import pytest

SOURCE=Path(__file__).parents[1]/'scripts/run_wl_catchup_673_20260906.py'


def gate():
    tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'require','inventory_ok'}]
    space={};exec(compile(ast.Module(nodes,type_ignores=[]),str(SOURCE),'exec'),space)
    return space['inventory_ok']


def inventory():
    return dict(all_physical_runs=699,eligible_runs=673,eligible_endpoints=18696,eligible_structural_pairs=4275,eligible_tasks=57)


def test_exact_inventory():gate()(inventory())


@pytest.mark.parametrize('key',list(inventory()))
@pytest.mark.parametrize('bad',[None,True,0,'673'])
def test_drift_refuses_before_launch(key,bad):
    value=inventory();value[key]=bad
    with pytest.raises(RuntimeError,match='inventory_drift'):gate()(value)


def test_fixed_one_pass_and_cleanup():
    text=SOURCE.read_text(encoding='utf-8')
    assert "WL_CHAIN_MAX_POLLS='1'" in text and 'timeout=7200' in text
    assert text.count('subprocess.Popen(')==1 and 'start_new_session=True' in text
    assert 'os.killpg(proc.pid,signal.SIGTERM)' in text and 'os.killpg(proc.pid,signal.SIGKILL)' in text
    assert 'monitor_transition_snapshot_chain' not in text
    assert "SCORER_COMMIT='031edb34400781ca026bc9833ac7f850312ffb1c'" in text


def test_safe_postcheck_never_deserializes_predictions():
    text=SOURCE.read_text(encoding='utf-8')
    for forbidden in ('torch.load','numpy.load','np.load','endpoint_scores.jsonl','pair_predictions.jsonl','accuracy['):
        assert forbidden not in text
    assert "json.loads((root/'monitor_receipt.json').read_bytes())" in text
