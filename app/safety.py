"""Injection and personal-data screening.

Two independent risks from ``06_SAFETY_COST_ENGINEERING.md``:

* a lecture that contains instruction-like text must not steer the model;
* audio may contain a name, email, phone number or student ID.

Both are *flagged*, never silently rewritten: the transcript shown to the
student stays the transcript, and the report says what was found. Masking is an
explicit display option, not a mutation of the evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION_PATTERNS = (
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above) instructions?",
    r"disregard (?:all |any )?(?:the )?(?:previous|prior|above) (?:instructions?|rules?)",
    r"system prompt",
    r"you are now",
    r"reveal (?:your|the) (?:prompt|instructions?|system)",
    r"forget (?:everything|all) (?:you|above)",
    r"jailbreak",
)

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){9,12}\d(?!\d)")
_IDENTIFIER = re.compile(r"\b[A-Z]{2,4}[-/]?\d{5,10}\b")

_INJECTION = re.compile("|".join(f"(?:{pattern})" for pattern in INJECTION_PATTERNS), re.IGNORECASE)


@dataclass(frozen=True)
class SafetyFinding:
    kind: str  # "injection" | "email" | "phone" | "identifier"
    text: str
    start: int
    end: int


def scan_injection(text: str) -> list[SafetyFinding]:
    """Flag instruction-like phrases in the lecture text."""
    return [
        SafetyFinding(kind="injection", text=match.group(0), start=match.start(), end=match.end())
        for match in _INJECTION.finditer(text or "")
    ]


def scan_pii(text: str) -> list[SafetyFinding]:
    """Flag emails, phone numbers and student-ID-shaped strings."""
    findings: list[SafetyFinding] = []
    for kind, pattern in (
        ("email", _EMAIL),
        ("phone", _PHONE),
        ("identifier", _IDENTIFIER),
    ):
        for match in pattern.finditer(text or ""):
            findings.append(
                SafetyFinding(kind=kind, text=match.group(0), start=match.start(), end=match.end())
            )
    return sorted(findings, key=lambda finding: (finding.start, finding.end))


def mask(text: str, findings: list[SafetyFinding]) -> str:
    """Replace each finding's span with a label, leaving everything else intact.

    Applied only to the *displayed* copy, so the verification evidence keeps the
    original transcript text.
    """
    masked = text or ""
    for finding in sorted(findings, key=lambda item: item.start, reverse=True):
        masked = masked[: finding.start] + f"[redacted-{finding.kind}]" + masked[finding.end :]
    return masked


def scan_all(text: str) -> list[SafetyFinding]:
    return sorted(scan_injection(text) + scan_pii(text), key=lambda finding: finding.start)
