"""Executor abstraction: how GhostQA observes and drives an app under test."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..state.models import GUIState, Action


@dataclass
class ExecResult:
    """Result of executing one action."""
    ok: bool                              # action was executable
    state: Optional[GUIState] = None      # resulting state (None if crashed)
    crashed: bool = False                 # app crashed / fatal
    js_errors: list = field(default_factory=list)
    http_errors: list = field(default_factory=list)
    events: list = field(default_factory=list)   # domain events (e.g. "cart_changed")
    message: str = ""


class Executor(ABC):
    """Drives one instance of the app under test."""

    @abstractmethod
    def observe(self) -> GUIState:
        """Capture current GUI state."""

    @abstractmethod
    def execute(self, action: Action) -> ExecResult:
        """Execute an action and return the result with the new state."""

    @abstractmethod
    def reset(self) -> GUIState:
        """Restart the app to its initial state."""

    @abstractmethod
    def ground_truth(self) -> dict:
        """Internal ground-truth data for oracle evaluation (sim: direct; web: DOM-derived)."""


DEFAULT_INPUT_VOCAB = ["", "测试输入", "x" * 25, "<script>alert(1)</script>", "999999", "-1"]


def available_actions(state: GUIState, can_back: bool,
                      input_vocab=None) -> list:
    """Constrained action space derived from the current state."""
    vocab = input_vocab if input_vocab is not None else DEFAULT_INPUT_VOCAB
    acts = []
    for el in state.elements:
        if not el.enabled:
            continue
        if el.kind == "click":
            acts.append(Action("click", el.eid))
        elif el.kind == "input":
            for v in vocab:
                acts.append(Action("input", el.eid, v))
    if can_back:
        acts.append(Action("back"))
    return acts
