"""Core data models for GhostQA. Pure stdlib, JSON-serializable."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass(frozen=True)
class UIElement:
    """A single interactable element on a screen."""
    eid: str            # stable identifier within a page
    role: str           # button | link | input | select | ...
    text: str           # visible text, truncated
    kind: str = "click"  # click | input
    enabled: bool = True
    input_type: str = ""      # html type: text/password/number/...
    placeholder: str = ""
    name: str = ""
    aria_label: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "UIElement":
        known = {"eid", "role", "text", "kind", "enabled",
                 "input_type", "placeholder", "name", "aria_label"}
        return UIElement(**{k: v for k, v in d.items() if k in known})


@dataclass
class GUIState:
    """An observed GUI state."""
    app: str
    url: str
    title: str
    elements: tuple = field(default_factory=tuple)   # tuple[UIElement]
    obs: dict = field(default_factory=dict)          # observable app data (rendered values)
    screenshot_ahash: Optional[int] = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "app": self.app, "url": self.url, "title": self.title,
            "elements": [e.to_dict() for e in self.elements],
            "obs": self.obs, "screenshot_ahash": self.screenshot_ahash,
            "meta": self.meta,
        }

    @staticmethod
    def from_dict(d: dict) -> "GUIState":
        return GUIState(
            app=d["app"], url=d["url"], title=d["title"],
            elements=tuple(UIElement.from_dict(e) for e in d["elements"]),
            obs=d.get("obs", {}), screenshot_ahash=d.get("screenshot_ahash"),
            meta=d.get("meta", {}),
        )


@dataclass(frozen=True)
class Action:
    """An executable action."""
    type: str                              # click | input | back | wait
    target_eid: Optional[str] = None
    text: Optional[str] = None             # input payload

    def key(self) -> str:
        return f"{self.type}:{self.target_eid or ''}:{self.text or ''}"

    def brief(self) -> str:
        if self.type == "input":
            return f'input[{self.target_eid}]="{self.text}"'
        if self.type == "click":
            return f"click[{self.target_eid}]"
        return self.type

    def to_dict(self) -> dict:
        return {"type": self.type, "target_eid": self.target_eid, "text": self.text}

    @staticmethod
    def from_dict(d: dict) -> "Action":
        return Action(type=d["type"], target_eid=d.get("target_eid"), text=d.get("text"))


@dataclass
class Finding:
    """An oracle finding (candidate bug before validation)."""
    kind: str           # crash | js_error | blank | dead_action | nav_loop | semantic
    severity: str       # high | medium | low
    description: str
    step_index: int
    evidence: dict = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Canonical BugFingerprint (see ghostqa.oracle.fingerprint)."""
        from ..oracle.fingerprint import fingerprint
        return fingerprint(self)

    def bug_key(self) -> str:
        """Deprecated alias kept for backward compatibility."""
        return self.fingerprint()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Step:
    """One exploration step record."""
    index: int
    state_sig_before: str
    action: Action
    state_sig_after: str
    findings: list = field(default_factory=list)   # list[Finding]
    episode_id: int = 0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "episode_id": self.episode_id,
            "state_sig_before": self.state_sig_before,
            "action": self.action.to_dict(),
            "state_sig_after": self.state_sig_after,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class ConfirmedBug:
    """A bug that passed replay validation (and possibly minimization)."""
    finding: Finding
    reproduction: list           # list[Action] minimal reproduction sequence
    original_length: int
    confirmed: bool = True

    def to_dict(self) -> dict:
        return {
            "finding": self.finding.to_dict(),
            "reproduction": [a.to_dict() for a in self.reproduction],
            "original_length": self.original_length,
            "confirmed": self.confirmed,
        }
