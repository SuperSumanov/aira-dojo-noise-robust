"""Budget/source projection of the fixed eight quarantined archives, no outcomes.

Reads only credential-screened dojo_config.json and tar headers; never extracts.
This does not admit physical runs, training data, or protected benchmark inputs.
"""
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import tarfile

from inspect_senior_quarantine_20260911 import ROOT, MANIFEST_SHA, SECRET, digest, unique, config_projection

NUMERIC = ('step_limit', 'num_children', 'num_children_to_choose', 'critic_top_k',
           'execution_timeout', 'time_limit_secs', 'max_llm_call_retries',
           'max_debug_depth', 'max_debug_time', 'uct_c')
TYPES = ('_dojo_dataclass_type', '_target_', 'name', 'type', 'search_policy', 'selection_policy')


def budget_projection(raw):
    base = config_projection(raw)
    if base['credential_refused']: raise ValueError('credential_in_config')
    cfg = json.loads(raw, object_pairs_hook=unique)
    solver = cfg['solver']
    out = {'git_commit_id': base['recorded_git_commit_id']}
    for key in NUMERIC:
        value = solver.get(key)
        if value is None:
            out[key] = None
        elif type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1e9:
            out[key] = value
        else:
            raise ValueError('non_numeric_budget_no_default_imputation')
    declared = {}
    for key in TYPES:
        value = solver.get(key)
        if value is None: continue
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,180}', value):
            raise ValueError('solver_type_not_public_code_identifier')
        declared[key] = value
    out['declared_solver_type_fields'] = declared
    # Presence is not proof of runtime class: save() uses untyped to_dict().
    out['uct_c_field_present'] = 'uct_c' in solver
    return out


def inspect(path):
    configs, headers, names = {}, [], set()
    total = 0
    with tarfile.open(path, 'r|gz') as archive:
        for index, member in enumerate(archive):
            pure = PurePosixPath(member.name)
            if index >= 100000 or pure.is_absolute() or '..' in pure.parts or '\\' in member.name:
                raise ValueError('unsafe_or_excess_member')
            if SECRET.search(member.name.encode()) or member.name in names: raise ValueError('member_name')
            names.add(member.name)
            if member.size < 0: raise ValueError('member_size')
            total += member.size
            if total > 2 * 1024**3: raise ValueError('expanded_limit')
            if member.islnk() or member.issym():
                headers.append((pure, 'unopened_link')); continue
            if not member.isfile(): continue
            if pure.name == 'journal.jsonl': headers.append((pure, 'journal_header'))
            if pure.name != 'dojo_config.json': continue
            if member.size > 2**20: raise ValueError('config_size')
            with archive.extractfile(member) as stream: raw = stream.read(2**20 + 1)
            configs[pure.parent] = (budget_projection(raw), hashlib.sha256(raw).hexdigest())
    owned = {p: Counter() for p in configs}
    orphan = Counter()
    for path, kind in headers:
        owners = [p for p in configs if path.is_relative_to(p)]
        if owners: owned[max(owners, key=lambda p: len(p.parts))][kind] += 1
        else: orphan[kind] += 1
    return [(cfg, sha, dict(owned[p])) for p, (cfg, sha) in configs.items()], dict(orphan)


def main():
    os.umask(0o077)
    def timeout(*_): raise TimeoutError('bounded_metadata_scan')
    signal.signal(signal.SIGALRM, timeout); signal.alarm(120)
    if digest(ROOT/'private_manifest.json') != MANIFEST_SHA: raise ValueError('manifest_drift')
    records = json.loads((ROOT/'private_manifest.json').read_bytes())['records']
    if len(records) != 8: raise ValueError('archive_scope')
    groups, all_hashes = {}, Counter()
    for record in records:
        rel = PurePosixPath(record['relative']); path = ROOT/'archives'/rel
        if rel.is_absolute() or '..' in rel.parts or path.is_symlink() or not path.resolve().is_relative_to(ROOT/'archives'):
            raise ValueError('archive_scope')
        if digest(path) != record['sha256']: raise ValueError('archive_drift')
        configs, orphan = inspect(path)
        if digest(path) != record['sha256']: raise ValueError('archive_changed')
        item = groups.setdefault(str(rel.parent), {'archives': 0, 'configurations': Counter(),
              'configs_with_journal_header': 0, 'configs_without_journal_header': 0,
              'configs_with_unopened_link': 0, 'orphan_headers': Counter()})
        item['archives'] += 1; item['orphan_headers'].update(orphan)
        for cfg, sha, headers in configs:
            item['configurations'][json.dumps(cfg, sort_keys=True)] += 1; all_hashes[sha] += 1
            item['configs_with_journal_header' if headers.get('journal_header') else 'configs_without_journal_header'] += 1
            item['configs_with_unopened_link'] += bool(headers.get('unopened_link'))
    for group in groups.values():
        group['configurations'] = [{'fields': json.loads(k), 'config_count': n}
                                    for k, n in sorted(group['configurations'].items())]
    result = {'status': 'BUDGET_METADATA_ONLY_NOT_RUNTIME_OR_TRAINING_ADMISSION',
              'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'manifest_sha256': MANIFEST_SHA,
              'script_sha256': digest(Path(__file__)), 'groups': groups,
              'byte_identical_config_duplicate_groups': sum(n > 1 for n in all_hashes.values()),
              'cross_existing_corpus_dedup_performed': False, 'physical_runs_validated': False,
              'archive_links_opened': False, 'journal_env_code_or_values_opened': False,
              'production_files_changed': False, 'archives_extracted': 0}
    raw = json.dumps(result, sort_keys=True, indent=2).encode()
    if SECRET.search(raw): raise ValueError('unsafe_public_projection')
    with (ROOT/'budget-metadata-summary.json').open('xb') as stream: stream.write(raw)
    print(raw.decode())


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'status': 'BUDGET_METADATA_FAILED_CLOSED', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
