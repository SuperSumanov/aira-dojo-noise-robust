"""Four fixes from the external audit, each verified against the source before changing it.

1. TF-IDF LEAKAGE (the champion row). The vectorizer was fit on train+test, so vocabulary
   selection, min_df and idf weights all saw held-out nodes. Fit on the training side only,
   then transform everything.

2. POST-EXECUTION FEATURES IN A DECISION-TIME PREDICTOR. `runtime` and `stdout_len` exist
   only after the program has run, yet they sat inside feats() priced at 0.3ms of query
   cost. That contradicts this paper's own claim that the self-report is expensive
   *because* it requires an execution. Remove them.

3. ONE-SIDED CLUSTERING. Pairs frequently span two runs, but the bootstrap clustered on the
   `better` endpoint's run alone. Report task-level clustering as primary (tasks are
   unambiguously independent) with the run-level number alongside.

4. NON-REPRODUCIBLE RANDOM BASELINE. hash() is salted per process; use crc32.
"""
import io

P = "phase1/predictor_suite.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)
Q = chr(34)

# ---- 2a: drop post-execution features from the decision-time set --------------
s = s.replace('        "runtime": float(fin(obs.get("runtime_s")) or 0.0),' + NL, "", 1)
s = s.replace('        "stdout_len": float(len(obs.get("stdout_tail") or "")),' + NL, "", 1)
assert '"runtime": float(fin' not in s and '"stdout_len"' not in s, "feature removal"

# ---- 2b: runtime leaves the zero-cost row list -------------------------------
old_zc = 'for f in ("code_len", "runtime", "n_lines", "depth", "step", "n_cv", "n_ensemble"):'
new_zc = 'for f in ("code_len", "n_lines", "depth", "step", "n_cv", "n_ensemble"):'
assert s.count(old_zc) == 1, "zc list"
s = s.replace(old_zc, new_zc, 1)

# ---- 4: reproducible random baseline -----------------------------------------
s = s.replace("import argparse, collections, json, math, random, re, statistics, time",
              "import argparse, collections, json, math, random, re, statistics, time, zlib", 1)
s = s.replace('evaluate("random", lambda b, w: random.Random(hash(b + w) & 0xffff).randint(0, 1), 0.0, 1e-6)',
              'evaluate("random", lambda b, w: zlib.crc32((b + w).encode()) & 1, 0.0, 1e-6)', 1)

# ---- 3: task-clustered CI as primary, run-clustered kept alongside -----------
old_ev = ("    per_run = collections.defaultdict(list)" + NL +
          "    n_cov = 0" + NL +
          "    t0 = time.time()" + NL +
          "    for p in test:" + NL +
          '        v = pred_fn(p["better"], p["worse"])' + NL +
          "        if v is None:" + NL +
          "            continue" + NL +
          "        n_cov += 1" + NL +
          '        per_run[RUN[p["better"]]].append(float(v))')
new_ev = ("    per_run = collections.defaultdict(list)" + NL +
          "    per_task = collections.defaultdict(list)" + NL +
          "    n_cov = 0" + NL +
          "    t0 = time.time()" + NL +
          "    for p in test:" + NL +
          '        v = pred_fn(p["better"], p["worse"])' + NL +
          "        if v is None:" + NL +
          "            continue" + NL +
          "        n_cov += 1" + NL +
          "        # a pair often spans two runs, so a run key taken from one endpoint" + NL +
          "        # understates dependence; task is an unambiguous independent unit" + NL +
          '        per_run[RUN[p["better"]]].append(float(v))' + NL +
          '        per_task[p["task"]].append(float(v))')
assert s.count(old_ev) == 1, "evaluate body"
s = s.replace(old_ev, new_ev, 1)

old_boot = ("    runs = list(per_run)" + NL +
            "    r = random.Random(7)" + NL +
            "    draws = []" + NL +
            "    for _ in range(2000):" + NL +
            "        s = [v for x in (r.choice(runs) for _ in runs) for v in per_run[x]]" + NL +
            "        draws.append(sum(s) / len(s))" + NL +
            "    draws.sort()" + NL +
            "    lo, hi = draws[50], draws[1950]")
new_boot = ("    def _boot(d):" + NL +
            "        ks = list(d)" + NL +
            "        rr = random.Random(7)" + NL +
            "        dr = []" + NL +
            "        for _ in range(2000):" + NL +
            "            ss = [v for x in (rr.choice(ks) for _ in ks) for v in d[x]]" + NL +
            "            dr.append(sum(ss) / len(ss))" + NL +
            "        dr.sort()" + NL +
            "        return dr[50], dr[1950]" + NL +
            "    lo, hi = _boot(per_task)          # primary: task-clustered" + NL +
            "    rlo, rhi = _boot(per_run)         # secondary: run-clustered, one endpoint")
assert s.count(old_boot) == 1, "bootstrap"
s = s.replace(old_boot, new_boot, 1)

s = s.replace('    results.append({"predictor": name, "acc": round(acc, 4),' + NL +
              '                    "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),',
              '    results.append({"predictor": name, "acc": round(acc, 4),' + NL +
              '                    "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),' + NL +
              '                    "ci_lo_run": round(rlo, 4), "ci_hi_run": round(rhi, 4),' + NL +
              '                    "n_tasks": len(per_task),', 1)

old_pr = '    print(f"{name:16s} acc={acc:.4f} [{lo:.4f},{hi:.4f}] "'
new_pr = ('    print(f"{name:16s} acc={acc:.4f} task[{lo:.4f},{hi:.4f}] '
          'run[{rlo:.4f},{rhi:.4f}] "')
assert s.count(old_pr) == 1, "print line"
s = s.replace(old_pr, new_pr, 1)

# ---- 1: fit the vectorizer on the training side only -------------------------
old_tf = ('ids = sorted({c for p in train + test for c in (p["better"], p["worse"])})' + NL +
          'tf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=30000,' + NL +
          "                     min_df=3, sublinear_tf=True)" + NL +
          'M = tf.fit_transform([(cards[c].get("code") or "")[:20000] for c in ids])')
new_tf = ('ids = sorted({c for p in train + test for c in (p["better"], p["worse"])})' + NL +
          'train_ids = sorted({c for p in train for c in (p["better"], p["worse"])})' + NL +
          'tf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=30000,' + NL +
          "                     min_df=3, sublinear_tf=True)" + NL +
          "# vocabulary, min_df and idf must come from the training side alone; fitting on" + NL +
          "# train+test let the champion row see held-out nodes" + NL +
          'tf.fit([(cards[c].get("code") or "")[:20000] for c in train_ids])' + NL +
          'M = tf.transform([(cards[c].get("code") or "")[:20000] for c in ids])')
assert s.count(old_tf) == 1, "tfidf"
s = s.replace(old_tf, new_tf, 1)

io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("predictor_suite.py fixed: tfidf leak, post-exec features, task-clustered CI, crc32")
