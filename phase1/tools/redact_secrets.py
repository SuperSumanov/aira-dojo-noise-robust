"""Redact secrets from run artifacts, in place, and sweep for copies elsewhere.

env_variables.json is a verbatim os.environ dump that dojo writes into every run directory, so
every run shipped the API keys alongside the data we intend to publish. This:

  1. rewrites every env_variables.json under the given roots, replacing any value whose KEY looks
     secret-ish (key/token/secret/pass/cred) or whose VALUE matches a known credential shape
     (sk-/hf_/ghp_/...) with REDACTED:sha256:<8>. The hash prefix keeps "same key or not"
     answerable (multi-account provenance) without the value; high-entropy secrets are safe to
     hash-prefix. Provenance fields like PC_CLIENT are untouched -- they were the evidence that
     exposed the gen2 bug and must survive.
  2. sweeps text-ish files under the roots for copies of the redacted VALUES (a log that echoed
     the environment would otherwise keep the leak alive) and reports paths only, never values.

Idempotent: already-redacted values are skipped, so it can run after every collection batch.
"""
import hashlib, json, os, re, sys

ROOTS = ["/research/d7/spc/yzyang4/aira-dojo-runs",
         "/research/d7/spc/yzyang4/logs"]
KEYPAT = re.compile(r"(key|token|secret|passwd|password|credential)", re.I)
VALPAT = re.compile(r"^(sk-|hf_|ghp_|gho_|glpat-|xoxb-|AKIA)[A-Za-z0-9._\-]{8,}")
TEXT_EXT = {".json", ".jsonl", ".log", ".out", ".txt", ".yaml", ".yml", ".sh", ".py", ".err"}

secrets = set()
targets = []
for root in ROOTS:
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if fn == "env_variables.json":
                targets.append(os.path.join(dp, fn))

nfile = nfield = 0
for f in targets:
    try:
        d = json.load(open(f))
    except Exception as e:
        print("SKIP unreadable:", f, e)
        continue
    changed = False
    for k, v in list(d.items()):
        if not isinstance(v, str) or not v or v.startswith("REDACTED:"):
            continue
        if KEYPAT.search(k) or VALPAT.match(v):
            secrets.add(v)
            d[k] = "REDACTED:sha256:" + hashlib.sha256(v.encode()).hexdigest()[:8]
            changed = True
            nfield += 1
    if changed:
        tmp = f + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh, indent=1)
        os.replace(tmp, f)
        nfile += 1
print(f"[redact] {nfield} fields across {nfile}/{len(targets)} env_variables.json files")

blobs = {s.encode() for s in secrets if len(s) >= 12}
hits = {}
scanned = 0
for root in ROOTS:
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            if fn == "env_variables.json" or os.path.splitext(fn)[1] not in TEXT_EXT:
                continue
            try:
                if os.path.getsize(p) > 300 * 1024 * 1024:
                    continue
                with open(p, "rb") as fh:
                    blob = fh.read()
            except Exception:
                continue
            scanned += 1
            n = sum(blob.count(b) for b in blobs)
            if n:
                hits[p] = n
print(f"[sweep] scanned {scanned} text files; {len(hits)} contain secret values:")
for p, n in sorted(hits.items())[:30]:
    print(f"   {n:3d}x {p}")
if len(hits) > 30:
    print(f"   ... and {len(hits) - 30} more")
