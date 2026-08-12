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
     the environment would otherwise keep the leak alive), replaces every copy atomically, and
     verifies that zero raw copies remain.  It reports paths/counts only, never values.

Idempotent: already-redacted values are skipped, so it can run after every collection batch.
"""
import hashlib, json, os, re, sys

import sys as _sys
ROOTS = _sys.argv[1:] or ["/research/d7/spc/yzyang4/aira-dojo-runs",
                          "/research/d7/spc/yzyang4/logs"]
KEYPAT = re.compile(r"(key|token|secret|passwd|password|credential)", re.I)
VALPAT = re.compile(r"^(sk-|hf_|ghp_|gho_|glpat-|xoxb-|AKIA)[A-Za-z0-9._\-]{8,}")
TEXT_EXT = {".json", ".jsonl", ".log", ".out", ".txt", ".yaml", ".yml", ".sh", ".py", ".err"}

secrets = {}
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
            replacement = "REDACTED:sha256:" + hashlib.sha256(v.encode()).hexdigest()[:8]
            secrets[v] = replacement
            d[k] = replacement
            changed = True
            nfield += 1
    if changed:
        tmp = f + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh, indent=1)
        os.replace(tmp, f)
        nfile += 1
print(f"[redact] {nfield} fields across {nfile}/{len(targets)} env_variables.json files")

blobs = {s.encode(): replacement.encode() for s, replacement in secrets.items()
         if len(s) >= 12}
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
                for secret, replacement in blobs.items():
                    blob = blob.replace(secret, replacement)
                tmp = p + ".redact-tmp"
                with open(tmp, "wb") as fh:
                    fh.write(blob)
                os.replace(tmp, p)
print(f"[sweep] scanned {scanned} text files; redacted {sum(hits.values())} raw copies "
      f"across {len(hits)} files:")
for p, n in sorted(hits.items())[:30]:
    print(f"   {n:3d}x {p}")
if len(hits) > 30:
    print(f"   ... and {len(hits) - 30} more")

remaining = {}
for root in ROOTS:
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            if os.path.splitext(fn)[1] not in TEXT_EXT:
                continue
            try:
                if os.path.getsize(p) > 300 * 1024 * 1024:
                    continue
                with open(p, "rb") as fh:
                    blob = fh.read()
            except Exception:
                continue
            n = sum(blob.count(secret) for secret in blobs)
            if n:
                remaining[p] = n
print(f"[verify] {len(remaining)} text files retain raw secret values")
if remaining:
    raise SystemExit(2)
