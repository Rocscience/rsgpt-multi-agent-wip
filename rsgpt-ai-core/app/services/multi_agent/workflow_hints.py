"""Goal-derived workflow hints (no product-specific hardcoded paths or values)."""

from __future__ import annotations

import re

_BEFORE_AFTER_GOAL_RE = re.compile(
    r"before.and.after|side.by.side|before/after|comparison of the results|"
    r"replace those common parameters|rerun.*comparison",
    re.I,
)

_MODEL_CREATION_GOAL_RE = re.compile(
    r"from\s+scratch|create\s+(?:a\s+)?(?:new\s+)?model|build\s+(?:a\s+)?model|"
    r"do\s+not\s+open|don't\s+open|without\s+opening|new\s+\w+\s+model|"
    r"blank\s+model|empty\s+model|start\s+from\s+scratch",
    re.I,
)


def goal_needs_before_after_comparison(goal: str) -> bool:
    """True when the user goal implies baseline + post-change result comparison."""
    return bool(_BEFORE_AFTER_GOAL_RE.search(goal or ""))


def path_is_absent(file_path: str) -> bool:
    """True when no usable model file path was provided (incl. planner n/a typos)."""
    p = (file_path or "").strip().strip('"').strip("'")
    if not p:
        return True
    norm = p.replace("\\", "/").lower()
    return norm in ("n/a", "na", "none", "null")


def goal_is_model_creation(goal: str, file_path: str = "") -> bool:
    """
    True when the user wants to configure a product without opening an example file.

    Triggered by explicit from-scratch language or by missing file path combined with
    creation-oriented wording.
    """
    g = goal or ""
    if _MODEL_CREATION_GOAL_RE.search(g):
        return True
    if path_is_absent(file_path) and re.search(
        r"create|configure|define|set up|setup|build|scratch|new model",
        g,
        re.I,
    ):
        return True
    return False
