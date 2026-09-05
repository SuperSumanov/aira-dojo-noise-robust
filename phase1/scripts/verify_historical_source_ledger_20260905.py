"""Independently join stored source receipts; no journal/config payload reads."""
import collections
import hashlib
import json
from pathlib import Path

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE / 'historical-source-ledger-faf04cc-20260905'
MAPPING = BASE / 'historical-repair-config-3044f0a-20260905-A/combined_mapping.private.json'


def h(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode() + b'\n'


def main():
    raw = MAPPING.read_bytes()
    assert h(raw) == 'fd8e0769f4561937f2959c055da18120e3715aaf3b772364cca72e1a4268aec6'
    mapping = json.loads(raw)
    ledger_raw = (ROOT / 'source_ledger.private.json').read_bytes()
    ledger = json.loads(ledger_raw)
    summary = json.loads((ROOT / 'summary.json').read_bytes())
    assert h(ledger_raw) == summary['ledger_sha256']
    assert set(ledger) == set(mapping) and len(ledger) == 676
    archive_receipts = {}
    for path in ROOT.glob('archive-*.private.json'):
        receipt = json.loads(path.read_bytes())
        sha = receipt['archive_sha256']
        assert sha not in archive_receipts
        archive_receipts[sha] = receipt
    groups = collections.defaultdict(set)
    expected_origins = set()
    for rid, expected_rows in mapping.items():
        assert len(ledger[rid]['origins']) == len(expected_rows)
        for old, origin in zip(expected_rows, ledger[rid]['origins']):
            assert all(origin[k] == v for k, v in old.items())
            receipt = archive_receipts[old['archive_sha256']]
            assert all(origin[k] == v for k, v in receipt['configs'][rid].items())
            assert all(origin[k] == v for k, v in receipt['journals'][rid].items())
            assert origin['journal_member'] == str(Path(origin['config_member']).parent/'checkpoint/journal.jsonl')
            assert type(origin['original_hold']) is bool
            assert origin['journal_bytes'] > 0
            expected_origins.add((old['archive_sha256'], old['config_member'], old['config_sha256']))
            groups[('batch', old['archive_sha256'], old['config_member'].split('/')[0])].add(rid)
            groups[('meta', old['recorded_meta_id'])].add(rid)
    assert len(expected_origins) == 676
    # Non-union-find independent graph traversal of the conservative closure.
    adjacency = {rid: set() for rid in mapping}
    for group in groups.values():
        for rid in group:
            adjacency[rid].update(group)
    remaining = set(mapping)
    components = []
    counts = collections.Counter()
    tasks = set()
    while remaining:
        seed = min(remaining); stack = [seed]; found = set()
        while stack:
            rid = stack.pop()
            if rid in found:
                continue
            found.add(rid); stack.extend(adjacency[rid] - found)
        remaining -= found
        group_sha = h(canonical(sorted(found)))
        blocked = any(mapping[rid][0]['original_hold'] for rid in found)
        for rid in found:
            assert ledger[rid]['conservative_component_sha256'] == group_sha
            assert ledger[rid]['old_hold_closure_blocks_train'] == blocked
            counts['blocked_runs' if blocked else 'clear_runs_not_admitted'] += 1
        counts['blocked_components' if blocked else 'clear_components_not_admitted'] += 1
        components.append(found)
    assert len(components) == summary['conservative_components']
    control = Path('/tmp/historical-ledger-control-faf04cc-KMkdOH')
    assert (control/'exit_status.txt').read_text().strip() == '0'
    trace = (control/'opens.private.log').read_bytes()
    assert b'journal.jsonl"' not in trace and b'env_variables.json"' not in trace
    result = {'status': 'INDEPENDENT_SOURCE_LEDGER_JOIN_AND_HOLD_CLOSURE_VERIFIED',
              'runs': len(mapping), 'unique_archive_member_config_origins': len(expected_origins),
              'archive_receipts': len(archive_receipts), 'components': len(components),
              'hold_closure': dict(counts), 'ledger_sha256': h(ledger_raw),
              'trace_sha256': h(trace), 'input_records_and_original_holds_preserved': True,
              'raw_journal_payloads_or_outcome_fields_read_by_verifier': 0,
              'pristine_execution_or_experiment_truth_attested': False,
              'old_S0_overridden': False, 'training_source_qualified': False}
    with (ROOT/'independent_summary.json').open('x') as handle:
        handle.write(json.dumps(result, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
