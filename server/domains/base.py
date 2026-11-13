"""Domain plug-in contract. A domain is one synthetic business (company, accounts, tool allowlist, verifier).

Tool specs share one shape: {"kind": read|mutation|verify|safe, "risk": low|medium|high, "params": [...],
"description": "..."} plus "ok_key" on verify tools (the boolean the verifier reports). Every account-scoped tool
takes `account_id`, whatever the domain calls the record, so the generic extractor/executor need no per-domain code.
"""
from typing import Any, Optional

from ..db import Store

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

# The one tool every domain shares: hand the case to a human channel. Risk low, no state change.
ESCALATE_TOOL = {"kind": "safe", "risk": "low", "params": ["case_id", "channel"], "description": "Hand the case to a human channel"}


def max_risk(risks) -> str:
    best = "low"
    for r in risks:
        if RISK_ORDER.get(r, 0) > RISK_ORDER[best]:
            best = r
    return best


def ok_result(output: Any, before: Optional[dict], after: Optional[dict]) -> dict:
    return {"success": True, "output": output, "before": before, "after": after, "error": None}


def failed_result(output: Any, before: Optional[dict], error: str = "PRECONDITION_FAILED") -> dict:
    return {"success": False, "output": output, "before": before, "after": before, "error": error}


class Domain:
    """Base class; subclasses fill the class attributes and implement the four hooks."""

    id: str = ""
    display_name: str = ""
    company: str = ""
    prefix: str = ""                  # account id prefix, e.g. "C" or "N"
    noun: str = "account"             # how the domain names its records in customer-facing text
    tools: dict = {}
    profile_tool: str = ""            # read tool the executor uses to evaluate field prerequisites
    entitlement_tool: str = ""        # read tool whose {"eligible": true} output becomes a prerequisite
    default_feature: str = ""
    prereq_fields: tuple = ()         # profile fields that may become hard prerequisites
    degraded_field: str = ""          # fault-injection flag that makes the verifier fail
    default_intent: str = ""
    vocabulary: dict = {}             # sector words -> matcher concepts ("internet" -> "data"); reviewer-editable, see resolve/matcher.py
    intent_examples: tuple = ()       # canonical phrasings of the problem (from the runbook) that seed a learned playbook's match examples
    escalation_options: list = []
    already_ok_message: str = ""

    def seed_rows(self) -> list:
        """Return the account dicts (without tenant_id/timestamps) this domain seeds on reset."""
        raise NotImplementedError

    def public_profile(self, acc: dict) -> dict:
        raise NotImplementedError

    def entitlement(self, acc: dict, feature: str) -> dict:
        raise NotImplementedError

    def invoke(self, store: Store, tenant_id: str, tool_id: str, params: dict, acc: Optional[dict], before: Optional[dict]) -> dict:
        """Run one allowlisted, already-authorised tool and return {success, output, before, after, error}."""
        raise NotImplementedError

    def status(self, acc: dict) -> dict:
        """Customer-facing status summary for /v1/accounts/{id}/status."""
        raise NotImplementedError

    def draft_prerequisites(self) -> list:
        """Prerequisites an LLM or fallback draft falls back to when the model proposes none."""
        return []

    # ---- helpers shared by subclasses ----
    def verify_tools(self) -> list:
        return [t for t, s in self.tools.items() if s["kind"] == "verify"]

    def tool_summary(self) -> list:
        return [{"id": t, "kind": s["kind"], "risk": s.get("risk", "low"), "description": s.get("description", "")} for t, s in self.tools.items()]
