"""Agent repair contract: a stable code, a plain-language fix, and a docs
pointer on every expected failure. Modelled on Solid 2.0's agent diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass

DOCS = "docs/diagnostics.md"

# code -> the one-line fix shown to the caller
CATALOG: dict[str, str] = {
    "SKMCP_EMPTY_INPUT": "send non-blank text, a non-blank name, or a non-blank query",
    "SKMCP_INPUT_TOO_LARGE": "chunk the input upstream; the server refuses instead of truncating",
    "SKMCP_ENGINE_REJECTED": "fix the request using the engine detail; do not retry it unchanged",
    "SKMCP_ENGINE_UNREACHABLE": "start skills-engine and check SKILLS_ENGINE_URL",
    "SKMCP_ENGINE_5XX": "retry after the engine recovers; GETs already retried once",
    "SKMCP_ENGINE_BAD_RESPONSE": "check the engine response body; it was not valid JSON",
}


@dataclass(frozen=True)
class Diagnostic(ValueError):
    """A caller-fixable failure. Inherits ValueError so existing handlers work."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if self.code not in CATALOG:
            raise ValueError(f"undocumented diagnostic code: {self.code}")

    @property
    def hint(self) -> str:
        return CATALOG[self.code]

    @property
    def docs(self) -> str:
        return f"{DOCS}#{self.code.casefold()}"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "docs": self.docs,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (fix: {self.hint}) (docs: {self.docs})"
