"""Experiment "card" schema + (i) live/offline construction from aira-dojo journals and
(ii) a numeric featurizer used by the mock/tabular critic backends.

A Card bundles what a critic MAY see (task / code / obs / lineage) and, separately, the LABEL
(expensive MLE-bench graded score). ``Card.view()`` / ``Card.hidden()`` strip the label so it can
never leak into a critic's input; the label is used only to fit targets and to score predictions.

Semantics chosen this round (assumption #1 = option B, confirmed): each aira-dojo node is ONE run;
obs = the candidate's self-reported validation at whatever fidelity the agent used; label.graded =
that same run's external MLE-bench grade. See README.md "Assumptions / TODO" for fidelity/val_curve
fields that aira-dojo does NOT natively record.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import numpy as np

OPS = ["Draft", "Debug", "Improve"]
TASK_TYPES = ["image-cls", "tabular", "nlp"]


@dataclass
class TaskInfo:
    name: str
    type: str = "tabular"
    metric: str = "auc"
    higher_is_better: bool = True
    desc: str = ""
    medal_thresholds: Dict[str, float] = field(default_factory=dict)  # {"gold":..,"silver":..,"bronze":..}


@dataclass
class Obs:
    fidelity: Dict[str, Any] = field(default_factory=lambda: {"epochs": None, "data_frac": None})
    val_curve: List[float] = field(default_factory=list)
    val_at_low: Optional[float] = None
    runtime_s: Optional[float] = None
    error: Optional[str] = None
    stdout_tail: str = ""


@dataclass
class Lineage:
    parent_val: Optional[float] = None
    op: str = "Draft"
    depth: int = 0                       # legacy: number of parents (0/1). Kept for feature stability.
    parent_id: Optional[str] = None      # card id of the parent node ("" root -> None)
    tree_depth: Optional[int] = None     # true depth from root (root=0), computed per journal
    children_ids: List[str] = field(default_factory=list)
    n_siblings: Optional[int] = None     # siblings sharing the same parent (excluding self)
    step: Optional[int] = None           # journal step index (tree build order)


@dataclass
class Label:
    graded: Optional[float] = None      # raw MLE-bench graded score
    y_norm: Optional[float] = None      # normalized to [0,1] by medal thresholds (per task)
    medal_bucket: str = "none"          # none|bronze|silver|gold


@dataclass
class Card:
    id: str
    task: TaskInfo
    code: str = ""
    obs: Obs = field(default_factory=Obs)
    lineage: Lineage = field(default_factory=Lineage)
    label: Optional[Label] = None

    # ---- label hiding ----
    def view(self) -> Dict[str, Any]:
        """Everything a critic MAY read (never the label)."""
        return {"id": self.id, "task": asdict(self.task), "code": self.code,
                "obs": asdict(self.obs), "lineage": asdict(self.lineage)}

    def hidden(self) -> "Card":
        """A copy with the label removed (passed to Critic.predict)."""
        return Card(id=self.id, task=self.task, code=self.code, obs=self.obs, lineage=self.lineage, label=None)

    @property
    def y(self) -> Optional[float]:
        return self.label.y_norm if self.label else None

    def to_json(self) -> Dict[str, Any]:
        d = {"id": self.id, "task": asdict(self.task), "code": self.code,
             "obs": asdict(self.obs), "lineage": asdict(self.lineage)}
        if self.label is not None:
            d["label"] = asdict(self.label)
        return d

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "Card":
        return cls(
            id=d["id"], task=TaskInfo(**d["task"]), code=d.get("code", ""),
            obs=Obs(**d.get("obs", {})), lineage=Lineage(**d.get("lineage", {})),
            label=Label(**d["label"]) if d.get("label") is not None else None,
        )


# ---------------------------------------------------------------------------
# Numeric featurizer (for mock / tabular critic backends; the real Qwen critics
# use the raw text instead — see critics/*.py).
# ---------------------------------------------------------------------------
FEATURE_NAMES = (
    ["val_at_low", "parent_val", "val_minus_parent", "depth", "epochs", "data_frac",
     "runtime_log", "has_error", "curve_n", "curve_last", "curve_delta", "curve_slope", "curve_mean",
     "code_len_log", "code_nlines_log", "higher_is_better"]
    + [f"op_{o}" for o in OPS]
    + [f"type_{t}" for t in TASK_TYPES]
)


def _f(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def card_features(card: Card) -> np.ndarray:
    o, ln, tk = card.obs, card.lineage, card.task
    curve = [c for c in (o.val_curve or []) if c is not None]
    if len(curve) >= 2:
        c_last, c_delta = curve[-1], curve[-1] - curve[0]
        c_slope = (curve[-1] - curve[0]) / (len(curve) - 1)
        c_mean = float(np.mean(curve))
    else:
        c_last = _f(o.val_at_low)
        c_delta = c_slope = 0.0
        c_mean = _f(o.val_at_low)
    parent = _f(ln.parent_val, _f(o.val_at_low))
    feats = [
        _f(o.val_at_low), parent, _f(o.val_at_low) - parent, _f(ln.depth),
        _f((o.fidelity or {}).get("epochs")), _f((o.fidelity or {}).get("data_frac")),
        math.log1p(_f(o.runtime_s)), 1.0 if o.error else 0.0,
        float(len(curve)), c_last, c_delta, c_slope, c_mean,
        math.log1p(len(card.code or "")), math.log1p((card.code or "").count("\n")),
        1.0 if tk.higher_is_better else 0.0,
    ]
    feats += [1.0 if ln.op == o_ else 0.0 for o_ in OPS]
    feats += [1.0 if tk.type == t_ else 0.0 for t_ in TASK_TYPES]
    return np.asarray(feats, dtype=float)


def features_matrix(cards: List[Card]) -> np.ndarray:
    return np.vstack([card_features(c) for c in cards]) if cards else np.zeros((0, len(FEATURE_NAMES)))


# ---------------------------------------------------------------------------
# Label normalization by medal thresholds (per task)
# ---------------------------------------------------------------------------
def normalize_graded(graded: float, thr: Dict[str, float], higher_is_better: bool) -> tuple:
    """Map a raw graded score to y_norm in [0,1] using medal thresholds, and a medal bucket.

    Piecewise-linear against {bronze,silver,gold}; robust to lower-is-better metrics. If thresholds
    are missing, falls back to a pass-through clamp (documented in README as a degraded path).
    """
    b, s, g = thr.get("bronze"), thr.get("silver"), thr.get("gold")
    if None in (b, s, g):
        return (None, "none")
    # orient so "better" is larger
    sign = 1.0 if higher_is_better else -1.0
    x, b, s, g = sign * graded, sign * b, sign * s, sign * g
    # bucket
    if x >= g:
        bucket = "gold"
    elif x >= s:
        bucket = "silver"
    elif x >= b:
        bucket = "bronze"
    else:
        bucket = "none"
    # piecewise-linear y in [0,1]: none-region -> [0,.33] anchored below bronze by span (s-b)
    span = max(1e-9, s - b)
    lo = b - span  # anchor for y=0
    y = (x - lo) / max(1e-9, (g - lo))
    return (float(min(1.0, max(0.0, y))), bucket)


# ---------------------------------------------------------------------------
# Build cards from an aira-dojo journal.jsonl  (offline post-parse; best-effort).
# Live-hook variant: call card_from_node_data(get_node_data(i), task_meta) inside a solver callback.
# ---------------------------------------------------------------------------
def card_from_node_data(nd: Dict[str, Any], task: TaskInfo) -> Optional[Card]:
    """One aira-dojo journal node dict (see journal.get_node_data) -> Card. Returns None for root."""
    mi = nd.get("metric_info") or {}
    if nd.get("code", "") == "" and nd.get("step") == 0:
        return None  # root node
    graded = mi.get("score")                       # external MLE-bench grade (non-hce runs)
    self_val = mi.get("validation_score", nd.get("metric"))  # self-reported val (use_test_score path)
    thr = {k: mi.get(f"{k}_threshold") for k in ("gold", "silver", "bronze")}
    # refine the task from the grade record itself: real mle-bench metric_info carries
    # competition_id + is_lower_better + *_threshold (verified against actual MCTS journals).
    tk = asdict(task)
    if mi.get("competition_id"):
        tk["name"] = mi["competition_id"]
        if not tk.get("desc"):
            tk["desc"] = mi["competition_id"]
    if mi.get("is_lower_better") is not None:
        tk["higher_is_better"] = not bool(mi.get("is_lower_better"))
    if any(v is not None for v in thr.values()):
        tk["medal_thresholds"] = {k: v for k, v in thr.items() if v is not None}
    task = TaskInfo(**tk)
    y_norm, bucket = (None, "none")
    if graded is not None and task.medal_thresholds:
        y_norm, bucket = normalize_graded(graded, task.medal_thresholds, task.higher_is_better)
    label = Label(graded=graded, y_norm=y_norm, medal_bucket=bucket) if graded is not None else None
    return Card(
        id=f"{task.name}__{nd.get('id', nd.get('step'))}",
        task=task, code=nd.get("code", ""),
        # TODO(aira-dojo has no native fidelity/val-curve): epochs/data_frac/val_curve unknown ->
        # left None/[]; would require injecting logging into generated code (see README assumption #2).
        obs=Obs(fidelity={"epochs": None, "data_frac": None}, val_curve=[],
                val_at_low=self_val, runtime_s=nd.get("exec_time"),
                error=(None if nd.get("exit_code") == 0 else "exec_error"),
                stdout_tail=(nd.get("term_out") or "")[-800:]),
        lineage=Lineage(parent_val=None, op=(nd.get("operators_used") or ["Draft"])[0].capitalize(),
                        depth=int(nd.get("depth", len(nd.get("parents") or [])))),
        label=label,
    )


def parse_journal(path: str, task: TaskInfo) -> List[Card]:
    """Offline: read a run's checkpoint/journal.jsonl -> list[Card] (skips root & label-less nodes)."""
    nodes = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                nodes.append(json.loads(line))
    by_step = {n.get("step"): n for n in nodes}

    def _cid(step):
        n = by_step.get(step)
        return f"{task.name}__{n.get('id', n.get('step'))}" if n else None

    # true depth from root, walking `parents` (index-into-step); cycle-safe
    def _tree_depth(step, _seen=None):
        _seen = _seen or set()
        if step in _seen:
            return None
        n = by_step.get(step)
        if n is None:
            return None
        ps = n.get("parents") or []
        if not ps:
            return 0
        d = _tree_depth(ps[0], _seen | {step})
        return None if d is None else d + 1

    kids_of = {}
    for n in nodes:
        for p in (n.get("parents") or []):
            kids_of.setdefault(p, []).append(n.get("step"))

    cards = []
    for nd in nodes:
        c = card_from_node_data(nd, task)
        if c is None:
            continue
        step = nd.get("step")
        parents = nd.get("parents") or []
        if parents and parents[0] in by_step:
            pmi = (by_step[parents[0]].get("metric_info") or {})
            c.lineage.parent_val = pmi.get("validation_score", by_step[parents[0]].get("metric"))
            c.lineage.parent_id = _cid(parents[0])
            sibs = kids_of.get(parents[0], [])
            c.lineage.n_siblings = max(0, len(sibs) - 1)
        c.lineage.step = step
        c.lineage.tree_depth = _tree_depth(step)
        c.lineage.children_ids = [x for x in (_cid(k) for k in kids_of.get(step, [])) if x]
        cards.append(c)
    return cards


def save_cards(cards: List[Card], path: str) -> None:
    with open(path, "w") as f:
        for c in cards:
            f.write(json.dumps(c.to_json()) + "\n")


def load_cards(path: str) -> List[Card]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(Card.from_json(json.loads(line)))
    return out
