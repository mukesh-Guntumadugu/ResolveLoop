"""Domain "saas": Orbit Analytics / Orbit Reports. The original ResolveLoop demo business, unchanged in behaviour.

Tool ids, account ids (C001..C016), outputs and error codes (EXP-100/200/500) are exactly what the live eGain agent
expects; this module only wraps them in the Domain contract.
"""
from typing import Optional

from ..common import ApiError, now_iso
from ..db import Store
from .base import ESCALATE_TOOL, Domain, failed_result, ok_result

EXPORT_ROLES = ("analyst", "admin")

TOOLS: dict = {
    "accounts.get_profile": {"kind": "read", "risk": "low", "params": ["account_id"], "description": "Read the synthetic account profile"},
    "accounts.check_entitlement": {"kind": "read", "risk": "low", "params": ["account_id", "feature"], "description": "Is the account entitled to a feature by plan, role and subscription?"},
    "accounts.grant_export_permission": {"kind": "mutation", "risk": "low", "params": ["account_id"], "description": "Set export_permission=true for an entitled, migrated, active account"},
    "reports.test_export": {"kind": "verify", "risk": "low", "ok_key": "export_ok", "params": ["account_id"], "description": "Run a test export and report whether it succeeded"},
    "cases.escalate": ESCALATE_TOOL,
}

SEED_ACCOUNTS = [
    # id, active, role, migrated, export_permission, plan
    ("C001", True, "analyst", True, False, "Team"),
    ("C002", True, "analyst", True, False, "Team"),
    ("C003", False, "analyst", True, False, "Team"),
    ("C004", True, "analyst", True, False, "Business"),
    ("C005", True, "admin", True, False, "Business"),
    ("C006", True, "analyst", True, False, "Starter"),
    ("C007", True, "admin", True, False, "Team"),
    ("C008", True, "analyst", True, False, "Team"),
    ("C009", True, "analyst", True, True, "Team"),
    ("C010", True, "analyst", True, True, "Business"),
    ("C011", True, "admin", True, True, "Team"),
    ("C012", False, "admin", True, False, "Team"),
    ("C013", True, "viewer", True, False, "Team"),
    ("C014", True, "analyst", False, False, "Team"),
    ("C015", True, "analyst", True, False, "Team"),
    ("C016", True, "analyst", True, None, "Team"),
]


class SaasDomain(Domain):
    id = "saas"
    display_name = "Orbit Reports"
    company = "Orbit Analytics"
    prefix = "C"
    noun = "account"
    tools = TOOLS
    profile_tool = "accounts.get_profile"
    entitlement_tool = "accounts.check_entitlement"
    default_feature = "export"
    prereq_fields = ("active", "role", "migrated", "export_permission")
    degraded_field = "export_service_degraded"
    default_intent = "export_blocked_after_migration"
    escalation_options = ["email ticket to support@orbit-analytics.example", "phone or callback (555) 010-0199"]
    already_ok_message = "Your account already has export enabled and a test export succeeds. No change was needed."

    def seed_rows(self) -> list:
        return [{"id": i, "active": a, "role": r, "migrated": m, "export_permission": p, "plan": pl, "export_service_degraded": False}
                for i, a, r, m, p, pl in SEED_ACCOUNTS]

    def public_profile(self, acc: dict) -> dict:
        return {k: acc.get(k) for k in ("active", "role", "migrated", "export_permission", "plan")}

    def entitlement(self, acc: dict, feature: str) -> dict:
        if feature != "export":
            return {"eligible": False, "reason": f"unknown feature '{feature}'"}
        if not acc.get("active"):
            return {"eligible": False, "reason": "subscription inactive (EXP-200)"}
        if acc.get("role") not in EXPORT_ROLES:
            return {"eligible": False, "reason": f"role '{acc.get('role')}' cannot export; analysts and admins only"}
        if acc.get("export_permission") is None:
            return {"eligible": False, "reason": "export permission state unknown; needs human review"}
        return {"eligible": True, "reason": f"plan {acc.get('plan')} with role {acc.get('role')} on an active subscription"}

    def invoke(self, store: Store, tenant_id: str, tool_id: str, params: dict, acc: Optional[dict], before: Optional[dict]) -> dict:
        if tool_id == "accounts.get_profile":
            return ok_result(before, before, before)
        if tool_id == "accounts.check_entitlement":
            return ok_result(self.entitlement(acc, params.get("feature", "")), before, before)
        if tool_id == "accounts.grant_export_permission":
            ent = self.entitlement(acc, "export")
            if not ent["eligible"]:
                return failed_result({"granted": False, "reason": ent["reason"]}, before)
            if not acc.get("migrated"):
                return failed_result({"granted": False, "reason": "account is not migrated; this remedy only applies after migration"}, before)
            if acc.get("export_permission") is True:
                return ok_result({"granted": True, "changed": False, "reason": "already enabled"}, before, before)
            acc["export_permission"] = True
            acc["updated_at"] = now_iso()
            store.put("account", acc)
            return ok_result({"granted": True, "changed": True}, before, self.public_profile(acc))
        if tool_id == "reports.test_export":
            ok = bool(acc.get("active")) and acc.get("role") in EXPORT_ROLES and acc.get("export_permission") is True \
                and not acc.get("export_service_degraded")
            if ok:
                out = {"export_ok": True, "error_code": None}
            elif not acc.get("active"):
                out = {"export_ok": False, "error_code": "EXP-200"}
            elif acc.get("export_permission") is not True or acc.get("role") not in EXPORT_ROLES:
                out = {"export_ok": False, "error_code": "EXP-100"}
            else:
                out = {"export_ok": False, "error_code": "EXP-500"}
            return ok_result(out, before, before)
        raise ApiError(400, "TOOL_NOT_IMPLEMENTED", tool_id)

    def status(self, acc: dict) -> dict:
        p = self.public_profile(acc)
        if not p["active"]:
            summary = "Subscription inactive: the workspace is read-only and exports are disabled (EXP-200)."
        elif p["role"] == "viewer":
            summary = "Active subscription. Viewer role: can open dashboards but cannot export."
        elif p["export_permission"] is True:
            summary = f"Active {p['plan']} subscription, {p['role']} role, export enabled."
        elif p["export_permission"] is None:
            summary = "Active subscription but the export permission state is unknown; a specialist must review it."
        else:
            summary = f"Active {p['plan']} subscription, {p['role']} role, but export permission is OFF" + (" after the Orbit Cloud 2 migration." if p["migrated"] else ".")
        return {"account_id": acc["id"], **p, "summary": summary}

    def draft_prerequisites(self) -> list:
        return [{"field": "active", "op": "==", "value": True}, {"field": "migrated", "op": "==", "value": True},
                {"tool": "accounts.check_entitlement", "params": {"feature": "export"}, "expect": {"eligible": True}}]
