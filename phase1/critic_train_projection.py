"""Read only explicitly pinned, already-admitted TRAIN projection files.

This reader is not a producer/evaluator/source qualification authority. Its
bindings must come from a separately reviewed release, not from an untrusted
manifest next to the data. It never opens the original corpus or a dev/test
file, and a local-only plan never opens the global target file.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat

from phase1.global_local_execution_plan import EncoderBinding, PlanError
from phase1.global_local_training_inputs import prepare_training_inputs

HEX = re.compile(r'[0-9a-f]{64}')
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
MAX_BYTES = 1024**3


def require(ok, reason):
    if not ok:
        raise PlanError(reason)


def unique(items):
    out = {}
    for key, value in items:
        require(key not in out, 'projection_duplicate_json_key')
        out[key] = value
    return out


@dataclass(frozen=True)
class PinnedFile:
    name: str
    sha256: str
    size: int

    def __post_init__(self):
        require(type(self.name) is str and re.fullmatch(r'[a-z][a-z0-9_]*\.json', self.name), 'projection_filename')
        require(type(self.sha256) is str and HEX.fullmatch(self.sha256), 'projection_hash')
        require(type(self.size) is int and 0 < self.size <= MAX_BYTES, 'projection_size')


@dataclass(frozen=True)
class TrainProjectionSpec:
    source_package_sha256: str
    split_receipt_sha256: str
    topology: PinnedFile
    local_targets: PinnedFile
    global_targets: PinnedFile

    def __post_init__(self):
        require(all(type(x) is str and HEX.fullmatch(x) for x in
                    (self.source_package_sha256, self.split_receipt_sha256)), 'projection_source_binding')
        files = (self.topology, self.local_targets, self.global_targets)
        require(all(type(x) is PinnedFile for x in files), 'projection_file_binding')
        require(len({x.name for x in files}) == 3, 'projection_file_role_alias')


def read_pinned(root: Path, file: PinnedFile) -> dict:
    """Read the verified bytes once; parsing never reopens an unchecked path."""
    root = Path(root)
    require(root.is_absolute() and '..' not in root.parts, 'projection_absolute_root')
    require(not any(x.is_symlink() for x in (root, *root.parents)), 'projection_root_symlink')
    require(root.is_dir(), 'projection_root_missing')
    path = root/file.name
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == file.size,
            'projection_unsafe_or_wrong_size')
    with path.open('rb') as stream:
        import os
        opened = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'projection_open_race')
        raw = stream.read(file.size + 1)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    signature = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    # Windows path-stat and descriptor-stat can disagree on ctime. Compare
    # stability within each API, and bind their
    # identity/size across APIs; the expected byte hash is still mandatory.
    require(signature(before) == signature(final) and signature(opened) == signature(after)
            and before.st_size == opened.st_size, 'projection_changed')
    require(len(raw) == file.size and hashlib.sha256(raw).hexdigest() == file.sha256, 'projection_hash_drift')
    require(not SECRET.search(raw), 'projection_credential_shape')
    try:
        obj = json.loads(raw, object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(PlanError('projection_nonfinite_json')))
    except (UnicodeError, json.JSONDecodeError):
        raise PlanError('projection_json_invalid') from None
    require(type(obj) is dict, 'projection_json_object')
    return obj


def bind_header(obj, spec, protocol):
    require(obj.get('protocol') == protocol and obj.get('role') == 'train', 'projection_not_training_role')
    require(obj.get('source_package_sha256') == spec.source_package_sha256
            and obj.get('split_receipt_sha256') == spec.split_receipt_sha256, 'projection_release_mismatch')


def load_training_inputs(root, spec, tokenizer, *, encoder: EncoderBinding, protocol_sha256):
    require(type(spec) is TrainProjectionSpec, 'projection_spec_required')
    obj = read_pinned(Path(root), spec.topology)
    require(set(obj) == {'protocol', 'role', 'source_package_sha256', 'split_receipt_sha256',
                         'cards', 'global_edges', 'local_edges'}, 'projection_topology_schema')
    bind_header(obj, spec, 'critic-train-topology-v1')
    return prepare_training_inputs(obj['cards'], obj['global_edges'], obj['local_edges'], tokenizer,
                                   encoder=encoder, protocol_sha256=protocol_sha256)


def load_training_targets(root, spec, prepared, *, plan):
    """Use the validated plan to decide which target files may be opened."""
    require(type(spec) is TrainProjectionSpec, 'projection_spec_required')
    required = set(prepared.required_label_keys(plan))
    pool_keys = {source: {r.key for r in pool} for source, pool in zip(('G', 'L'), prepared.pools)}
    labels = {}
    for source, file in (('L', spec.local_targets), ('G', spec.global_targets)):
        needed = required & pool_keys[source]
        if not needed:
            continue
        obj = read_pinned(Path(root), file)
        require(set(obj) == {'protocol', 'role', 'source_package_sha256', 'split_receipt_sha256',
                             'source', 'winners'}, 'projection_target_schema')
        bind_header(obj, spec, 'critic-train-targets-v1')
        require(obj['source'] == source and type(obj['winners']) is dict, 'projection_target_source')
        # The files contain one admitted source's complete train target pool.
        # Required keys may be a prefix for an independently frozen schedule.
        require(set(obj['winners']) == pool_keys[source], 'projection_target_support')
        all_rows = {r.key: r for pool in prepared.pools for r in pool if r.source == source}
        require(all(type(w) is str and w in (all_rows[k].a.card_id, all_rows[k].b.card_id)
                    for k, w in obj['winners'].items()), 'projection_invalid_winner')
        labels.update({k: obj['winners'][k] for k in needed})
    return prepared.true_sign_provider(labels, plan=plan)
