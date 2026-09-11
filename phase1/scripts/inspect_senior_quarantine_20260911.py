"""Read archive headers and credential-screened dojo_config.json only.

No journals, code, labels, evaluation records, env dumps, or snapshots are opened.
Directory counts are NOT validated physical-run counts or training admission.
"""
from collections import Counter
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path('/research/d7/spc/yzyang4/senior-quarantine-20260911-v1')
MANIFEST_SHA = '67ac5406b789fa7a5a39f41e9483a095f671f2d25ba47ccf69af4f98264c7cb4'
ARCHIVE_COUNT = 8
SECRET = re.compile(rb'(?i)(?:^|[^a-z0-9])(?:sk-[a-z0-9._-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9a-z_-]{30,}|Bearer\s+[a-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''): h.update(block)
    return h.hexdigest()


def unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out: raise ValueError('duplicate_json_key')
        out[k] = v
    return out


def config_projection(raw):
    if not 0 < len(raw) <= 2**20: raise ValueError('config_size')
    if SECRET.search(raw): return {'credential_refused': True}
    cfg = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(cfg, dict): raise ValueError('config_object')
    meta = cfg.get('metadata', {})
    solver = cfg.get('solver', {})
    if not isinstance(meta, dict) or not isinstance(solver, dict): raise ValueError('config_schema')
    commit = meta.get('git_commit_id')
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit): commit = 'missing_or_unresolved'
    # Whitelist only code-entry names and integer step/width settings.
    projected = {}
    for k in ('_target_', 'name', 'type', 'search_policy', 'selection_policy'):
        value = solver.get(k)
        if isinstance(value, str) and re.fullmatch('[A-Za-z0-9_.-]{1,180}', value): projected[k] = value
    for k in ('num_steps', 'steps', 'num_children', 'max_steps'):
        value = solver.get(k)
        if type(value) is int and 0 <= value <= 100000: projected[k] = value
    return {'credential_refused': False, 'recorded_git_commit_id': commit, 'solver_fields': projected}


def inspect_archive(path):
    configs = []; dirs = set(); names = set(); opened = Counter(); header_counts = Counter()
    total = 0
    with tarfile.open(path, 'r|gz') as tar:
        for index, member in enumerate(tar):
            if index >= 100000: raise ValueError('member_limit')
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or '..' in pure.parts or '\\' in member.name or SECRET.search(member.name.encode()):
                raise ValueError('unsafe_member_name')
            if member.name in names: raise ValueError('duplicate_member')
            names.add(member.name)
            if member.size < 0: raise ValueError('negative_member_size')
            total += member.size
            if total > 2 * 1024**3: raise ValueError('expanded_size_limit')
            if member.issym() or member.islnk():
                header_counts['link_members_not_opened'] += 1
                continue
            if not member.isfile(): continue
            if pure.name in ('env_variables.json', 'journal.jsonl', 'dojo_config.json', 'producer.config_v2.jsonl'):
                header_counts[pure.name] += 1
            if pure.name != 'dojo_config.json': continue
            if member.size > 2**20: raise ValueError('config_size')
            with tar.extractfile(member) as stream: raw = stream.read(2**20 + 1)
            configs.append(config_projection(raw)); dirs.add(str(pure.parent)); opened['dojo_config.json'] += 1
    return configs, dirs, dict(opened), dict(header_counts)


def main():
    os.umask(0o077)
    manifest = ROOT / 'private_manifest.json'
    if digest(manifest) != MANIFEST_SHA: raise ValueError('manifest_drift')
    rows = json.loads(manifest.read_bytes())['records']
    if len(rows) != ARCHIVE_COUNT: raise ValueError('scope_count')
    groups = {}; all_dirs = set()
    for r in rows:
        rel = PurePosixPath(r['relative'])
        path = ROOT / 'archives' / rel
        if '..' in rel.parts or rel.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(ROOT / 'archives'):
            raise ValueError('archive_path')
        if digest(path) != r['sha256']: raise ValueError('archive_drift')
        configs, dirs, opened, headers = inspect_archive(path)
        if digest(path) != r['sha256']: raise ValueError('archive_changed')
        group = str(rel.parent)
        item = groups.setdefault(group, {'archives': 0, 'configs_opened': 0, 'credential_refused': 0,
                                        'config_parent_paths': set(), 'commits': Counter(), 'solver_configs': Counter(),
                                        'header_counts': Counter()})
        item['archives'] += 1; item['configs_opened'] += len(configs)
        item['header_counts'].update(headers)
        item['config_parent_paths'].update(dirs); all_dirs.update(dirs)
        for cfg in configs:
            if cfg['credential_refused']: item['credential_refused'] += 1; continue
            item['commits'][cfg['recorded_git_commit_id']] += 1
            item['solver_configs'][json.dumps(cfg['solver_fields'], sort_keys=True)] += 1
    for item in groups.values():
        item['distinct_config_parent_paths'] = len(item.pop('config_parent_paths'))
        item['solver_configs'] = [{'fields': json.loads(k), 'configs': n} for k, n in sorted(item['solver_configs'].items())]
    result = {'status': 'CONFIG_METADATA_ONLY_NOT_RUN_VALIDATION_OR_TRAINING',
              'quarantine_root': str(ROOT), 'archive_count_expected': ARCHIVE_COUNT,
              'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'manifest_sha256': MANIFEST_SHA,
              'script_sha256': digest(Path(__file__)), 'groups': groups,
              'cross_group_config_parent_path_overlap': sum(x['distinct_config_parent_paths'] for x in groups.values()) - len(all_dirs),
              'journals_env_code_outcomes_opened': False, 'protected_values_read': False,
              'archives_extracted': 0, 'production_source_changed': False}
    raw = json.dumps(result, sort_keys=True, indent=2).encode()
    if SECRET.search(raw): raise ValueError('public_output_secret_shape')
    with (ROOT / 'config-metadata-summary.json').open('xb') as f: f.write(raw)
    print(raw.decode())


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        # Never reveal archive member paths, raw configs, or unexpected exception strings.
        print(json.dumps({'status': 'CONFIG_METADATA_FAILED_CLOSED', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
