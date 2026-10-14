"""Common public-only preview and pre-request identity guard for NEW studies.

Never patches closed18253. Receipt files remain available to cleanup auditors;
they are simply not inputs to this explicit public-data preview. No model/GPU.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import time

TASKS = ('aerial-cactus-identification', 'denoising-dirty-documents')
PREVIEW_SOURCE_SHA = 'c153a875e5517b32a78aebf11da88efe2170d80d14db427451e7570859860d27'
DONOR_PLAN_SHA = 'cba9bad500a106b8c44f18116c491a1744edb50c3744c7f7ef1f498e45cdbd4f'
FORBIDDEN = re.compile(r'kernel-shutdown-guard|Kernel did not become ready|TimeoutError:|Traceback \(most recent|^ERROR:', re.M)
SECRET = re.compile(r'\bsk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._-]{16,}', re.I)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def validate_text(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 6200:
        raise ValueError('missing or oversized public preview')
    if FORBIDDEN.search(text) or SECRET.search(text):
        raise ValueError('runtime diagnostic or credential-shaped preview refused')
    return text


def public_manifest(public):
    """Caller passes only the validated public view, never its parent/siblings."""
    public = Path(public).resolve(strict=True)
    files = []
    for p in sorted(public.rglob('*')):
        if p.is_symlink():
            raise ValueError('public-view child symlink refused')
        if p.is_file():
            files.append(dict(path=p.relative_to(public).as_posix(), bytes=p.stat().st_size, sha256=sha(p)))
    if not files:
        raise ValueError('empty public view')
    return files


def build(donor, output):
    donor, output = Path(donor), Path(output)
    if output.exists():
        raise FileExistsError('preview bundle is immutable')
    plan_bytes = (donor/'plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    if (hashlib.sha256(plan_bytes).hexdigest() != DONOR_PLAN_SHA or
            plan.get('planned') != 32 or not (donor/'closed.json').is_file()):
        raise ValueError('expected closed32 donor')
    source = donor/'source/src/dojo/core/solvers/utils/data_preview.py'
    if sha(source) != PREVIEW_SOURCE_SHA:
        raise ValueError('native public preview source drift')
    spec = importlib.util.spec_from_file_location('pinned_native_public_preview', source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    started = time.monotonic(); rows = {}
    for task in TASKS:
        configs = [json.loads((donor/f"configs/{s['index']}.json").read_text())
                   for s in plan['schedule'] if s['task'] == task]
        public = (donor/'dev-views'/task/'public').resolve(strict=True)
        if not configs or any(Path(c['task']['public_dir']).resolve() != public or
                              Path(c['task']['data_dir']).resolve() != public for c in configs):
            raise ValueError('public view differs between conditions')
        before = public_manifest(public)
        with tempfile.TemporaryDirectory(prefix='public-preview-') as folder:
            work = Path(folder)
            (work/'data').symlink_to(public, target_is_directory=True)
            (work/'input_cache').mkdir()
            text = validate_text(module.generate(work))
            if module.generate(work) != text:
                raise ValueError('non-deterministic native preview')
        if public_manifest(public) != before:
            raise ValueError('public data changed during preview freeze')
        rows[task] = dict(text=text, text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                          public_path=str(public), public_manifest_sha256=digest(before),
                          public_files=len(before))
    bundle = dict(schema=1, donor_plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
                  native_preview_source_sha256=PREVIEW_SOURCE_SHA, tasks=rows,
                  preparation_wall_seconds=time.monotonic()-started,
                  scope='Only public training/query files; no private references, outcomes, history, model calls or GPU. Common setup, not search quality.')
    with output.open('x') as f:
        json.dump(bundle, f, sort_keys=True, indent=2, allow_nan=False)
    output.chmod(0o600)
    return dict(bundle_sha256=sha(output), tasks={k: {n:v for n,v in row.items() if n != 'text'} for k,row in rows.items()},
                preparation_wall_seconds=bundle['preparation_wall_seconds'], gpu_calls=0, model_calls=0)


def load_text(bundle, expected_sha, task):
    if sha(bundle) != expected_sha:
        raise ValueError('frozen preview bundle drift')
    value = json.loads(Path(bundle).read_text())
    if value['schema'] != 1 or value['native_preview_source_sha256'] != PREVIEW_SOURCE_SHA or task not in TASKS:
        raise ValueError('unexpected public preview contract')
    row = value['tasks'][task]
    text = validate_text(row['text'])
    if hashlib.sha256(text.encode()).hexdigest() != row['text_sha256']:
        raise ValueError('frozen preview text drift')
    return text


class FirstRequestGuard:
    """Wrap client.query AFTER native prompt rendering, BEFORE any transport.

    A rejected first request cannot be rescued by a later request. Later search
    inputs may legitimately diverge; this never forces equal post-treatment paths.
    """
    def __init__(self, expected_sha, record):
        if re.fullmatch('[a-f0-9]{64}', expected_sha) is None:
            raise ValueError('expected real-input prompt digest required')
        self.expected_sha, self.record = expected_sha, record
        self.seen = False
        self.failed = False

    def check(self, messages):
        if self.failed:
            raise ValueError('first request already rejected')
        if self.seen:
            return
        observed = digest(messages)
        self.failed = observed != self.expected_sha
        self.record(dict(event='first_request_input_gate', sha256=observed,
                         expected_sha256=self.expected_sha, passed=not self.failed))
        if self.failed:
            raise ValueError('actual first request/history differs before transport')
        self.seen = True

    def wrap(self, query):
        async def guarded(messages, *args, **kwargs):
            self.check(messages)
            return await query(messages, *args, **kwargs)
        return guarded


def install(mcts_class, llm_class, text, expected_prompt_sha, record):
    """New-study-only hook: same public preview and a shared first-request gate.

    Must be installed after common runtime hooks, before constructing any LLM.
    No sandbox/cleanup code is changed or disabled by this input-only hook.
    """
    text = validate_text(text)
    guard = FirstRequestGuard(expected_prompt_sha, record)
    def preview(self, state):
        self.data_preview = text
        record(dict(event='fixed_public_preview_loaded',
                    sha256=hashlib.sha256(text.encode()).hexdigest()))
    mcts_class.update_data_preview = preview
    original_init = llm_class.__init__
    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.client.query = guard.wrap(self.client.query)
    llm_class.__init__ = init
    return guard


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('donor'); ap.add_argument('output')
    args = ap.parse_args()
    print(json.dumps(build(args.donor, args.output), sort_keys=True))
