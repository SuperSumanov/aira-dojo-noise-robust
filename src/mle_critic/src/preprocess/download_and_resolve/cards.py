"""Card data model and conversion utilities for aira-dojo journals.

Each journal node, including the empty root, becomes one :class:`Card`. A Card stores the task,
natural-language plan, code, execution observation, and position in the search tree. Its MLE-bench
grade is stored separately in ``label``. ``Card.view()`` and ``Card.hidden()`` deliberately omit
that label so it cannot leak into critic inputs.

This module also contains the legacy numeric featurizer used by mock/tabular critic backends. Text
critics consume the raw Card fields instead.
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
    depth: int = 0                       # legacy journal depth; fallback is parent count. Kept stable.
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
    plan: str = ""
    code: str = ""
    obs: Obs = field(default_factory=Obs)
    lineage: Lineage = field(default_factory=Lineage)
    label: Optional[Label] = None

    # ---- label hiding ----
    def view(self) -> Dict[str, Any]:
        """Everything a critic MAY read (never the label)."""
        return {
            "id": self.id,
            "task": asdict(self.task),
            "plan": self.plan,
            "code": self.code,
            "obs": asdict(self.obs),
            "lineage": asdict(self.lineage),
        }

    def hidden(self) -> "Card":
        """A copy with the label removed (passed to Critic.predict)."""
        return Card(
            id=self.id,
            task=self.task,
            plan=self.plan,
            code=self.code,
            obs=self.obs,
            lineage=self.lineage,
            label=None,
        )

    @property
    def y(self) -> Optional[float]:
        return self.label.y_norm if self.label else None

    def to_json(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "task": asdict(self.task),
            "plan": self.plan,
            "code": self.code,
            "obs": asdict(self.obs),
            "lineage": asdict(self.lineage),
            "label": asdict(self.label) if self.label is not None else None,
        }
        return d

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "Card":
        return cls(
            id=d["id"], task=TaskInfo(**d["task"]), plan=d.get("plan", ""),
            code=d.get("code", ""),
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


def _finite_float(value, default=0.0):
    """Convert a value to a finite float, returning ``default`` when that is impossible."""
    try:
        converted_value = float(value)
        return converted_value if math.isfinite(converted_value) else default
    except (TypeError, ValueError):
        return default


def card_features(card: Card) -> np.ndarray:
    observation = card.obs
    lineage = card.lineage
    task = card.task
    validation_curve = [value for value in (observation.val_curve or []) if value is not None]
    if len(validation_curve) >= 2:
        curve_last = validation_curve[-1]
        curve_delta = validation_curve[-1] - validation_curve[0]
        curve_slope = curve_delta / (len(validation_curve) - 1)
        curve_mean = float(np.mean(validation_curve))
    else:
        curve_last = _finite_float(observation.val_at_low)
        curve_delta = curve_slope = 0.0
        curve_mean = _finite_float(observation.val_at_low)
    validation_score = _finite_float(observation.val_at_low)
    parent_validation_score = _finite_float(lineage.parent_val, validation_score)
    features = [
        validation_score, parent_validation_score, validation_score - parent_validation_score,
        _finite_float(lineage.depth),
        _finite_float((observation.fidelity or {}).get("epochs")),
        _finite_float((observation.fidelity or {}).get("data_frac")),
        math.log1p(_finite_float(observation.runtime_s)), 1.0 if observation.error else 0.0,
        float(len(validation_curve)), curve_last, curve_delta, curve_slope, curve_mean,
        math.log1p(len(card.code or "")), math.log1p((card.code or "").count("\n")),
        1.0 if task.higher_is_better else 0.0,
    ]
    features += [1.0 if lineage.op == operation else 0.0 for operation in OPS]
    features += [1.0 if task.type == task_type else 0.0 for task_type in TASK_TYPES]
    return np.asarray(features, dtype=float)


def features_matrix(cards: List[Card]) -> np.ndarray:
    return (
        np.vstack([card_features(card) for card in cards])
        if cards
        else np.zeros((0, len(FEATURE_NAMES)))
    )


# ---------------------------------------------------------------------------
# Label normalization by medal thresholds (per task)
# ---------------------------------------------------------------------------
def normalize_graded(
    graded_score: float,
    medal_thresholds: Dict[str, float],
    higher_is_better: bool,
) -> tuple:
    """Map a raw graded score to y_norm in [0,1] using medal thresholds, and a medal bucket.

    Piecewise-linear against {bronze,silver,gold}; robust to lower-is-better metrics. Returns
    ``(None, "none")`` when any threshold is missing because no comparable target can be built.
    """
    bronze = medal_thresholds.get("bronze")
    silver = medal_thresholds.get("silver")
    gold = medal_thresholds.get("gold")
    if None in (bronze, silver, gold):
        return (None, "none")

    # Put both higher-is-better and lower-is-better metrics on an axis where larger is better.
    sign = 1.0 if higher_is_better else -1.0
    oriented_score = sign * graded_score
    oriented_bronze = sign * bronze
    oriented_silver = sign * silver
    oriented_gold = sign * gold

    if oriented_score >= oriented_gold:
        medal_bucket = "gold"
    elif oriented_score >= oriented_silver:
        medal_bucket = "silver"
    elif oriented_score >= oriented_bronze:
        medal_bucket = "bronze"
    else:
        medal_bucket = "none"

    # Use one bronze-to-silver interval below bronze as the zero point, then linearly map up to
    # gold. Scores outside this interval are clipped to [0, 1].
    bronze_to_silver_span = max(1e-9, oriented_silver - oriented_bronze)
    zero_score = oriented_bronze - bronze_to_silver_span
    normalized_score = (oriented_score - zero_score) / max(1e-9, oriented_gold - zero_score)
    normalized_score = float(min(1.0, max(0.0, normalized_score)))
    return (normalized_score, medal_bucket)


# ---------------------------------------------------------------------------
# Build cards from an aira-dojo journal.jsonl  (offline post-parse; best-effort).
# Live-hook variant: call card_from_node_data(get_node_data(i), task_meta) inside a solver callback.
# ---------------------------------------------------------------------------
def card_from_node_data(node_data: Dict[str, Any], task: TaskInfo) -> Card:
    """Convert one aira-dojo journal node to a Card, including empty and unlabeled nodes."""
    metric_info = node_data.get("metric_info") or {}

    # ``validation_score`` is produced by the candidate's own validation. ``score`` is the
    # expensive external MLE-bench grade and must remain in Card.label only.
    graded_score = metric_info.get("score")
    validation_score = metric_info.get("validation_score", node_data.get("metric"))
    journal_thresholds = {
        medal: metric_info.get(f"{medal}_threshold")
        for medal in ("gold", "silver", "bronze")
    }

    # The caller supplies fallback task metadata. A real MLE-bench grade record is more
    # authoritative, so use its competition id, metric direction, and medal thresholds when set.
    task_fields = asdict(task)
    competition_id = metric_info.get("competition_id")
    if competition_id:
        task_fields["name"] = competition_id
        if not task_fields.get("desc"):
            task_fields["desc"] = competition_id
    if metric_info.get("is_lower_better") is not None:
        task_fields["higher_is_better"] = not bool(metric_info["is_lower_better"])
    if any(threshold is not None for threshold in journal_thresholds.values()):
        task_fields["medal_thresholds"] = {
            medal: threshold
            for medal, threshold in journal_thresholds.items()
            if threshold is not None
        }
    resolved_task = TaskInfo(**task_fields)

    normalized_score, medal_bucket = (None, "none")
    if graded_score is not None and resolved_task.medal_thresholds:
        normalized_score, medal_bucket = normalize_graded(
            graded_score,
            resolved_task.medal_thresholds,
            resolved_task.higher_is_better,
        )
    label = (
        Label(graded=graded_score, y_norm=normalized_score, medal_bucket=medal_bucket)
        if graded_score is not None
        else None
    )
    operators_used = node_data.get("operators_used") or ["Draft"]
    return Card(
        id=f"{resolved_task.name}__{node_data.get('id', node_data.get('step'))}",
        task=resolved_task,
        plan=node_data.get("plan") or "",
        code=node_data.get("code") or "",
        # TODO(aira-dojo has no native fidelity/val-curve): epochs/data_frac/val_curve unknown ->
        # left None/[]; would require injecting logging into generated code (see README assumption #2).
        obs=Obs(
            fidelity={"epochs": None, "data_frac": None},
            val_curve=[],
            val_at_low=validation_score,
            runtime_s=node_data.get("exec_time"),
            error=(
                "exec_error"
                if node_data.get("exit_code") is not None and node_data.get("exit_code") != 0
                else None
            ),
            stdout_tail=(node_data.get("term_out") or "")[-800:],
        ),
        lineage=Lineage(
            parent_val=None,
            op=operators_used[0].capitalize(),
            # This legacy field comes from the journal when available. parse_journal computes the
            # unambiguous root-relative depth separately as ``tree_depth``.
            depth=int(node_data.get("depth", len(node_data.get("parents") or []))),
        ),
        label=label,
    )


def parse_journal(path: str, task: TaskInfo) -> List[Card]:
    """Read one journal and convert every node to a Card, including its root."""
    journal_nodes = []
    with open(path) as journal_file:
        for line in journal_file:
            stripped_line = line.strip()
            if stripped_line:
                journal_nodes.append(json.loads(stripped_line))
    node_by_step = {node.get("step"): node for node in journal_nodes}

    def card_id_for_step(step):
        node = node_by_step.get(step)
        return f"{task.name}__{node.get('id', node.get('step'))}" if node else None

    def tree_depth_from_root(step, visited_steps=None):
        """Follow the first-parent chain; return None for missing nodes or parent cycles."""
        visited_steps = visited_steps or set()
        if step in visited_steps:
            return None
        node = node_by_step.get(step)
        if node is None:
            return None
        parent_steps = node.get("parents") or []
        if not parent_steps:
            return 0
        parent_depth = tree_depth_from_root(parent_steps[0], visited_steps | {step})
        return None if parent_depth is None else parent_depth + 1

    child_steps_by_parent = {}
    for node in journal_nodes:
        for parent_step in node.get("parents") or []:
            child_steps_by_parent.setdefault(parent_step, []).append(node.get("step"))

    cards = []
    for node in journal_nodes:
        card = card_from_node_data(node, task)
        step = node.get("step")
        parent_steps = node.get("parents") or []
        if parent_steps and parent_steps[0] in node_by_step:
            parent_step = parent_steps[0]
            parent_node = node_by_step[parent_step]
            parent_metric_info = parent_node.get("metric_info") or {}
            card.lineage.parent_val = parent_metric_info.get(
                "validation_score", parent_node.get("metric")
            )
            card.lineage.parent_id = card_id_for_step(parent_step)
            sibling_steps = child_steps_by_parent.get(parent_step, [])
            card.lineage.n_siblings = max(0, len(sibling_steps) - 1)
        card.lineage.step = step
        card.lineage.tree_depth = tree_depth_from_root(step)
        card.lineage.children_ids = [
            child_card_id
            for child_card_id in (
                card_id_for_step(child_step)
                for child_step in child_steps_by_parent.get(step, [])
            )
            if child_card_id
        ]
        cards.append(card)
    return cards


def save_cards(cards_by_run_id: Dict[str, List[Card]], path: str) -> None:
    """Save all runs as one JSON object: ``run_id -> list[Card]``."""
    serialized_runs = {
        run_id: [card.to_json() for card in cards]
        for run_id, cards in cards_by_run_id.items()
    }
    with open(path, "w") as output_file:
        json.dump(serialized_runs, output_file)


def load_cards(path: str) -> Dict[str, List[Card]]:
    """Load the run-grouped JSON format written by :func:`save_cards`."""
    with open(path) as input_file:
        serialized_runs = json.load(input_file)
    if not isinstance(serialized_runs, dict):
        raise ValueError(f"Expected a JSON object mapping run IDs to cards: {path}")
    return {
        run_id: [Card.from_json(card_data) for card_data in serialized_cards]
        for run_id, serialized_cards in serialized_runs.items()
    }
