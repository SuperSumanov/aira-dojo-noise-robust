"""Aggregate date check on an already published historical header-only receipt.

Does not rescan archives, rerun S0, choose aliases, or access Cards/pairs/outcomes.
"""
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re

PATH = Path('/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3/producer_1/run_batch_manifest.jsonl')
EXPECTED = '60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'
FIELDS = {'run_id','task','original_hold','source_match_status','source_candidate_batches','source_day','batch_sha256'}
RUN = re.compile(r'^(.+_seed_[0-9]+_id_[0-9a-f]+)__(2026-\d{2}-\d{2})$')


def analyze(rows):
    counts, delays, seen = Counter(), Counter(), set()
    pairs = []
    for row in rows:
        if set(row) != FIELDS or row['run_id'] in seen:
            raise ValueError('schema_or_duplicate')
        match = RUN.fullmatch(row['run_id'])
        if match is None:
            raise ValueError('run_shape')
        seen.add(row['run_id'])
        launch = date.fromisoformat(match[2])
        state, n = row['source_match_status'], row['source_candidate_batches']
        if state not in ('unique','ambiguous','missing') or type(n) is not int:
            raise ValueError('source_state')
        counts[state] += 1
        if state != 'unique':
            if row['source_day'] is not None or row['batch_sha256'] is not None or not (n == 0 if state == 'missing' else n >= 2):
                raise ValueError('unresolved_not_empty')
            continue
        if n != 1 or re.fullmatch('[0-9a-f]{64}', row['batch_sha256']) is None:
            raise ValueError('invalid_unique')
        source = row['source_day']
        if not isinstance(source, str) or re.match(r'^\d{4}(?:-|$)', source) is None:
            raise ValueError('collection_directory_shape')
        collection = date(2026, int(source[:2]), int(source[2:4]))
        pairs.append((launch, collection))
        counts['unique_cross_date' if launch != collection else 'unique_same_date'] += 1
        delays[str((collection-launch).days)] += 1
    # Independent set-partition identity, rather than relying only on counters.
    equal = [p for p in pairs if p[0].isoformat() == p[1].isoformat()]
    unequal = [p for p in pairs if p[0].isoformat() != p[1].isoformat()]
    if len(pairs) != counts['unique'] or len(equal) != counts['unique_same_date'] or len(unequal) != counts['unique_cross_date']:
        raise ValueError('partition_inconsistent')
    return dict(rows=len(rows), run_source_status={s:counts[s] for s in ('unique','ambiguous','missing')},
                unique_same_date=counts['unique_same_date'], unique_cross_date=counts['unique_cross_date'],
                collection_minus_launch_days=dict(sorted(delays.items())),
                ambiguous_sources_resolved=0, missing_sources_resolved=0, old_S0_overridden=False)


def run():
    if PATH.is_symlink() or not PATH.is_file() or PATH.stat().st_size > 1024*1024:
        raise ValueError('unsafe_fixed_metadata')
    raw = PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError('historical_metadata_drift')
    if re.search(rb'(?i)(?:sk-[A-Za-z0-9_.-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})', raw):
        raise ValueError('credential_shape')
    rows = [json.loads(line) for line in raw.splitlines()]
    result = analyze(rows)
    if result['rows'] != 676 or analyze(list(reversed(rows))) != result:
        raise ValueError('inventory_or_order_drift')
    if hashlib.sha256(PATH.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('postcheck_drift')
    return dict(status='HISTORICAL_DATE_METADATA_DIAGNOSTIC_ONLY', input_sha256=EXPECTED,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), metrics=result,
                archive_payload_reads=0, archive_header_rescans=0, cards_or_pairs_opened=0,
                protected_cohort_reads=0, new_gpu_jobs=0, model_fits=0)


if __name__ == '__main__':
    try:
        print(json.dumps(run(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','exception_type':type(exc).__name__}))
        raise SystemExit(1)
