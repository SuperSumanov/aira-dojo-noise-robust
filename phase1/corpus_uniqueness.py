"""Independent recomputation of corpus uniqueness on the FULL v8 corpus.

The second of the two external numbers the four-elimination framing depends on. The audit
computed it on the 4,976 cards readable without LFS; we have all 12,383, and their own
caveat says a subset result does not settle it.

Three normalisations, because a single one proves nothing:
  raw       whitespace-collapsed source
  ast_norm  AST with every identifier and literal replaced by a placeholder -- kills
            renaming and constant tweaks
  skeleton  the sequence of AST node TYPES only -- kills everything except control and
            call structure. This is the strictest of the three; if programs are still
            mostly unique here, they are structurally distinct.

The lineage trap the audit flagged and this respects: roughly 70% of nodes come from the
Debug operator and are near-copies of their parent by construction. Any similarity number
computed without stratifying is measuring that mechanical resemblance. Duplicate groups are
therefore reported three ways -- overall, within a single run, and ACROSS runs. Only the
last speaks to whether the corpus rediscovers the same program independently.

Usage: python phase1/corpus_uniqueness.py [--cards cards_current_v8.jsonl]
"""
import argparse, ast, collections, hashlib, json, re

ap = argparse.ArgumentParser()
ap.add_argument("--cards", default="phase1/cards_current_v8.jsonl")
a = ap.parse_args()

RUN = json.load(open("phase1/card_run_map.json"))
rows = []
for l in open(a.cards):
    d = json.loads(l)
    c = d.get("code") or ""
    if c.strip():
        rows.append((d["id"], d["task"]["name"], d["lineage"].get("op"),
                     d["lineage"].get("parent_id"), c))
print(f"cards with code: {len(rows)}")
ops = collections.Counter(r[2] for r in rows)
print(f"operators: {dict(ops)}  "
      f"(Debug share {ops.get('Debug', 0) / len(rows):.1%} -- the mechanical-similarity trap)")

WS = re.compile(r"\s+")


def h(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:16]


class Norm(ast.NodeTransformer):
    """identifiers -> ID, literals -> LIT; structure survives, naming does not"""
    def visit_Name(self, n):
        return ast.copy_location(ast.Name(id="ID", ctx=n.ctx), n)

    def visit_arg(self, n):
        n.arg = "ID"
        n.annotation = None
        return n

    def visit_Attribute(self, n):
        self.generic_visit(n)
        n.attr = "ATTR"
        return n

    def visit_Constant(self, n):
        return ast.copy_location(ast.Constant(value="LIT"), n)

    def visit_FunctionDef(self, n):
        self.generic_visit(n)
        n.name = "FN"
        n.decorator_list = []
        return n

    def visit_ClassDef(self, n):
        self.generic_visit(n)
        n.name = "CLS"
        n.decorator_list = []
        return n


parsed = 0
sig = {"raw": {}, "ast_norm": {}, "skeleton": {}}
for cid, task, op, par, code in rows:
    sig["raw"][cid] = h(WS.sub(" ", code).strip())
    try:
        tree = ast.parse(code)
        parsed += 1
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        continue
    sig["skeleton"][cid] = h(",".join(type(n).__name__ for n in ast.walk(tree)))
    try:
        sig["ast_norm"][cid] = h(ast.dump(ast.fix_missing_locations(Norm().visit(tree)),
                                          annotate_fields=False))
    except (RecursionError, ValueError):
        pass
print(f"AST parse success: {parsed}/{len(rows)} = {parsed/len(rows):.1%}")

task_of = {r[0]: r[1] for r in rows}
parent_of = {r[0]: r[3] for r in rows}

print(f"\n{'normalisation':12s} {'n':>7} {'unique':>8} {'rate':>8} "
      f"{'dup grps':>9} {'largest':>8}")
for name in ("raw", "ast_norm", "skeleton"):
    m = sig[name]
    groups = collections.defaultdict(list)
    for cid, s in m.items():
        groups[s].append(cid)
    dup = {s: v for s, v in groups.items() if len(v) > 1}
    print(f"{name:12s} {len(m):7d} {len(groups):8d} {len(groups)/max(len(m),1):8.4f} "
          f"{len(dup):9d} {max((len(v) for v in dup.values()), default=0):8d}")

print("\nduplicate groups stratified by lineage (skeleton, the strictest):")
groups = collections.defaultdict(list)
for cid, s in sig["skeleton"].items():
    groups[s].append(cid)
dup = {s: v for s, v in groups.items() if len(v) > 1}
same_run = cross_run = parent_child = cross_task = 0
cross_run_examples = []
for s, v in dup.items():
    runs = {RUN.get(c) for c in v}
    tasks = {task_of[c] for c in v}
    pc = any(parent_of.get(x) == y or parent_of.get(y) == x
             for i, x in enumerate(v) for y in v[i + 1:])
    if pc:
        parent_child += 1
    if len(runs) == 1:
        same_run += 1
    else:
        cross_run += 1
        if len(cross_run_examples) < 5:
            cross_run_examples.append((len(v), len(runs), sorted(tasks)[0][:30]))
    if len(tasks) > 1:
        cross_task += 1
print(f"  total duplicate groups          {len(dup)}")
print(f"  confined to ONE run             {same_run}   <- mechanical, expected")
print(f"  containing a parent-child edge  {parent_child}   <- Debug near-copies")
print(f"  spanning TWO OR MORE runs       {cross_run}   <- the only ones that mean "
      f"'independently rediscovered'")
print(f"  spanning two or more tasks      {cross_task}   <- boilerplate")
if cross_run_examples:
    print(f"  cross-run examples (size, #runs, task): {cross_run_examples}")

nodes_in_cross = sum(len(v) for s, v in dup.items() if len({RUN.get(c) for c in v}) > 1)
print(f"\n  nodes inside cross-run duplicate groups: {nodes_in_cross} "
      f"({nodes_in_cross/max(len(sig['skeleton']),1):.2%} of parsed cards)")
print("  Read: a low cross-run figure means the corpus is not a few programs re-emitted,")
print("  which is what the redundancy elimination needs. A high within-run figure is")
print("  expected and says nothing -- Debug rewrites its parent.")

byt = collections.defaultdict(lambda: [0, 0])
for cid, s in sig["skeleton"].items():
    byt[task_of[cid]][1] += 1
for t, v in byt.items():
    v[0] = len({sig["skeleton"][c] for c in sig["skeleton"] if task_of[c] == t})
print(f"\n{'task':44s} {'cards':>7} {'unique skeletons':>17} {'rate':>7}")
for t, (u, n) in sorted(byt.items(), key=lambda kv: -kv[1][1]):
    print(f"{t[:44]:44s} {n:7d} {u:17d} {u/max(n,1):7.3f}")
