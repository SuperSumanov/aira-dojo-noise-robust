"""Leakage- and cluster-aware audit of the low-fidelity signal channel.

The original dose-response analysis compared policies on partially overlapping set
populations and bootstrapped parents.  This audit adds the strict comparison needed for
the mechanism claim: on candidates that expose both signals at 120 seconds, compare the
pristine external submission grade directly with the parsed self-reported score.  Ties
are handled by expected accuracy and inference is clustered by physical run and task.
"""

import argparse
import collections
import csv
import hashlib
import json
import math
import platform
import random
import subprocess
from pathlib import Path


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", default="phase1/cards_current_v9.jsonl")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-dir", default="phase1/dose_paired_rigor_v9")
    return parser.parse_args()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


args = arguments()
ROOT = str(Path(args.orientation).parent)
CARDS = args.cards
digest = hashlib.sha256()
with open(CARDS, "rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
if digest.hexdigest() != "daeb29fc07ad670b5ca7a10cd2d84f1fa9a27dfa9d22510533417f1a8ad9407f":
    raise RuntimeError("v9 corpus SHA mismatch")
ORI = json.load(open(args.orientation, encoding="utf-8"))
RUN = json.load(open(args.run_map, encoding="utf-8"))

truth = {}
full_self = {}
task = {}
for line in open(CARDS, encoding="utf-8"):
    row = json.loads(line)
    card = row["id"]
    task[card] = row["task"]["name"]
    for target, source, key in (
        (truth, row["label"], "graded"),
        (full_self, row["obs"], "val_at_low"),
    ):
        try:
            value = float(source.get(key))
            target[card] = value if math.isfinite(value) else None
        except (TypeError, ValueError):
            target[card] = None

cap = {}
children = collections.defaultdict(set)
stratum = {}
for line in open(args.results, encoding="utf-8"):
    row = json.loads(line)
    cap[row["card_id"], int(row["cap"])] = row
    children[row["parent"]].add(row["card_id"])
    stratum[row["parent"]] = row["stratum"]

reports = []
audit_rows = []


def utility(value, competition):
    return -float(value) if ORI.get(competition, False) else float(value)


def expected_hit(signal, target):
    if not signal:
        return None
    max_signal = max(signal.values())
    selected = [card for card, value in signal.items() if math.isclose(value, max_signal, abs_tol=1e-12)]
    max_truth = max(target.values())
    best = {card for card, value in target.items() if math.isclose(value, max_truth, abs_tol=1e-12)}
    return sum(card in best for card in selected) / len(selected)


def cluster_boot(rows, field, cluster="run"):
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row[cluster]].append(row[field])
    keys = sorted(grouped)
    rng = random.Random(args.seed)
    values = []
    for _ in range(args.bootstrap):
        sample = [rng.choice(keys) for _ in keys]
        flat = [value for key in sample for value in grouped[key]]
        values.append(sum(flat) / len(flat))
    values.sort()
    return values[int(.025 * args.bootstrap)], values[int(.975 * args.bootstrap)]


def report(label, rows):
    if not rows:
        print(label, "n=0")
        return
    delta = sum(row["delta"] for row in rows) / len(rows)
    a = sum(row["a"] for row in rows) / len(rows)
    b = sum(row["b"] for row in rows) / len(rows)
    lo, hi = cluster_boot(rows, "delta", "run")
    task_lo, task_hi = cluster_boot(rows, "delta", "task")
    by_run = collections.defaultdict(list)
    for row in rows:
        by_run[row["run"]].append(row["delta"])
    run_effects = [sum(values) / len(values) for values in by_run.values()]
    positive = sum(value > 0 for value in run_effects)
    negative = sum(value < 0 for value in run_effects)
    tied = sum(value == 0 for value in run_effects)
    informative = positive + negative
    smaller = min(positive, negative)
    tail = (
        sum(math.comb(informative, k) for k in range(smaller + 1)) / (2 ** informative)
        if informative
        else 0.5
    )
    sign_p = min(1.0, 2.0 * tail)
    reports.append({
        "comparison": label,
        "sets": len(rows),
        "runs": len(by_run),
        "tasks": len({row["task"] for row in rows}),
        "a": a,
        "b": b,
        "delta": delta,
        "run_cluster_ci95": [lo, hi],
        "task_cluster_ci95": [task_lo, task_hi],
        "run_sign_positive": positive,
        "run_sign_negative": negative,
        "run_sign_tied": tied,
        "run_sign_exact_p_two_sided": sign_p,
    })
    print(
        f"{label}: sets={len(rows)} runs={len(set(r['run'] for r in rows))} "
        f"A={a:.4f} B={b:.4f} delta={delta:+.4f} "
        f"runCI=[{lo:+.4f},{hi:+.4f}] taskCI=[{task_lo:+.4f},{task_hi:+.4f}]"
    )


def rows_for(mode, subset):
    output = []
    for parent in sorted(children):
        if subset != "ALL" and stratum[parent].upper() != subset:
            continue
        cards = sorted(card for card in children[parent] if truth.get(card) is not None)
        if len(cards) < 2:
            continue
        tasks = {task[card] for card in cards}
        runs = {RUN[card] for card in cards}
        if len(tasks) != 1 or len(runs) != 1:
            raise RuntimeError(parent)
        competition = next(iter(tasks))
        target = {card: utility(truth[card], competition) for card in cards}
        sub = {
            card: utility(cap[card, 120]["sub_score"], competition)
            for card in cards
            if (card, 120) in cap and cap[card, 120].get("sub_score") is not None
        }
        stdout = {
            card: utility(cap[card, 120]["stdout_val"], competition)
            for card in cards
            if (card, 120) in cap and cap[card, 120].get("stdout_val") is not None
        }
        full = {
            card: utility(full_self[card], competition)
            for card in cards if full_self.get(card) is not None
        }

        if mode == "policy_sub_vs_full":
            if not sub or len(full) != len(cards):
                continue
            sig_a, sig_b, eval_target = sub, full, target
        elif mode == "strict_sub_vs_full":
            common = sorted(set(sub) & set(full))
            if len(common) < 2:
                continue
            sig_a = {card: sub[card] for card in common}
            sig_b = {card: full[card] for card in common}
            eval_target = {card: target[card] for card in common}
        elif mode == "strict_sub_vs_stdout":
            common = sorted(set(sub) & set(stdout))
            if len(common) < 2:
                continue
            sig_a = {card: sub[card] for card in common}
            sig_b = {card: stdout[card] for card in common}
            eval_target = {card: target[card] for card in common}
        else:
            raise ValueError(mode)

        a = expected_hit(sig_a, eval_target)
        b = expected_hit(sig_b, eval_target)
        output.append({
            "parent": parent,
            "run": next(iter(runs)),
            "task": competition,
            "a": a,
            "b": b,
            "delta": a - b,
            "common": len(eval_target),
            "all": len(cards),
        })
    return output


for subset in ("ALL", "HARD", "EASY"):
    print("\n==", subset, "==")
    for mode in ("policy_sub_vs_full", "strict_sub_vs_full", "strict_sub_vs_stdout"):
        rows = rows_for(mode, subset)
        report(f"{subset}:{mode}", rows)
        if subset == "ALL":
            for row in rows:
                audit_rows.append({"comparison": mode, **row})
        if rows:
            print(
                "  common_candidates",
                collections.Counter(row["common"] for row in rows),
                "full_set_sizes",
                collections.Counter(row["all"] for row in rows),
            )
            if mode == "strict_sub_vs_stdout":
                by_task = collections.defaultdict(list)
                by_run = collections.defaultdict(list)
                for row in rows:
                    by_task[row["task"]].append(row["delta"])
                    by_run[row["run"]].append(row["delta"])
                print("  task_effects")
                for name in sorted(by_task):
                    values = by_task[name]
                    print(f"    {name}: n={len(values)} delta={sum(values)/len(values):+.4f}")
                run_effects = [sum(v) / len(v) for v in by_run.values()]
                pos = sum(value > 0 for value in run_effects)
                neg = sum(value < 0 for value in run_effects)
                tie = sum(value == 0 for value in run_effects)
                n = pos + neg
                tail = sum(math.comb(n, k) for k in range(min(pos, neg) + 1)) / (2 ** n) if n else 1.0
                p_two = min(1.0, 2 * tail)
                print(f"  run_sign positive={pos} negative={neg} tie={tie} exact_p={p_two:.6f}")
                loto = {}
                for held in sorted(by_task):
                    kept = [row["delta"] for row in rows if row["task"] != held]
                    loto[held] = sum(kept) / len(kept)
                print(
                    f"  LOTO min={min(loto.values()):+.4f} max={max(loto.values()):+.4f} "
                    f"all_positive={all(value > 0 for value in loto.values())}"
                )

print("\n== PARSER TYPES FOR STRICT COMMON @120 ==")
parser_types = collections.Counter()
common_cards = set()
for parent in sorted(children):
    cards = sorted(card for card in children[parent] if truth.get(card) is not None)
    sub = {card for card in cards if (card, 120) in cap and cap[card, 120].get("sub_score") is not None}
    stdout = {card for card in cards if (card, 120) in cap and cap[card, 120].get("stdout_val") is not None}
    common = sub & stdout
    if len(common) >= 2:
        common_cards.update(common)
for card in sorted(common_cards):
    parser_types[str(cap[card, 120].get("val_how"))] += 1
print("cards", len(common_cards), "val_how", parser_types)

out_dir = Path(args.out_dir)
out_dir.mkdir(parents=True, exist_ok=True)
with (out_dir / "per_set.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(audit_rows)

summary = {
    "provenance": {
        "inputs": {
            "cards": {"path": args.cards, "sha256": sha256(args.cards)},
            "orientation": {"path": args.orientation, "sha256": sha256(args.orientation)},
            "run_map": {"path": args.run_map, "sha256": sha256(args.run_map)},
            "results": {"path": args.results, "sha256": sha256(args.results)},
        },
        "script": {"path": __file__, "sha256": sha256(__file__)},
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "python": platform.python_version(),
        "command": (
            f"python {__file__} --cards {args.cards} --bootstrap {args.bootstrap} "
            f"--seed {args.seed} --out-dir {args.out_dir}"
        ),
    },
    "design": {
        "cap_s": 120,
        "strict_channel_comparison": (
            "same parent, same candidate subset exposing both sub_score and stdout_val"
        ),
        "tie_handling": "expected top-1 over all tied selected candidates",
        "clusters": ["physical run", "task"],
        "bootstrap_draws": args.bootstrap,
        "seed": args.seed,
        "confirmatory_status": "exploratory audit; requires prospective replication",
    },
    "comparisons": reports,
    "strict_common_parser_types": dict(sorted(parser_types.items())),
    "strict_common_cards": len(common_cards),
}
direct = next(row for row in reports if row["comparison"] == "ALL:strict_sub_vs_stdout")
summary["headline_candidate"] = direct
(out_dir / "summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(
    f"HEADLINE delta={direct['delta']:+.6f} "
    f"runCI={direct['run_cluster_ci95']} taskCI={direct['task_cluster_ci95']} "
    f"exact_run_sign_p={direct['run_sign_exact_p_two_sided']:.6f}"
)
print(f"WROTE {out_dir}")
