"""Domain "telecom": Nimbus Mobile. Lines (N001..N012) lose data roaming after the core network upgrade (CNU-5).

Mirror of the SaaS story: an entitled, upgraded, active line has roaming_enabled=False and the fix is a low-risk
re-provisioning. Two HIGH-risk tools (billing credit, ownership change) exist so the human-only gate has teeth.
Error codes: RM-100 roaming not provisioned, RM-200 plan has no roaming, RM-300 line suspended, RM-500 network fault.
"""
from typing import Optional

from ..common import ApiError, now_iso
from ..db import Store
from .base import ESCALATE_TOOL, Domain, failed_result, ok_result

ROAMING_PLANS = ("Plus", "Pro")

TOOLS: dict = {
    "lines.get_profile": {"kind": "read", "risk": "low", "params": ["account_id"], "description": "Read the synthetic line profile (account_id is the line id)"},
    "lines.check_entitlement": {"kind": "read", "risk": "low", "params": ["account_id", "feature"], "description": "Is the line entitled to a feature (roaming) by plan, add-on and status?"},
    "lines.enable_roaming": {"kind": "mutation", "risk": "low", "params": ["account_id"], "description": "Provision roaming on an entitled, upgraded, active line"},
    "network.test_roaming": {"kind": "verify", "risk": "low", "ok_key": "roaming_ok", "params": ["account_id"], "description": "Probe the roaming gateway for the line and report whether it attaches"},
    "billing.issue_credit": {"kind": "mutation", "risk": "high", "params": ["account_id", "amount"], "description": "Issue a bill credit to the line's account (human-only)"},
    "account.change_owner": {"kind": "mutation", "risk": "high", "params": ["account_id", "new_owner"], "description": "Transfer ownership of the line (human-only)"},
    "cases.escalate": ESCALATE_TOOL,
}

SEED_LINES = [
    # id, active, plan, roaming_addon, upgraded, roaming_enabled, owner_verified
    ("N001", True, "Plus", False, True, False, True),   # broken but eligible
    ("N002", True, "Plus", False, True, False, True),   # broken but eligible (paraphrase target)
    ("N003", False, "Plus", False, True, False, True),  # suspended (RM-300)
    ("N004", True, "Go", False, True, False, True),     # Go without add-on (RM-200)
    ("N005", True, "Pro", False, True, True, True),     # already enabled
    ("N006", True, "Plus", False, False, False, True),  # not upgraded yet
    ("N007", True, "Plus", False, True, None, True),    # roaming state unknown
    ("N008", True, "Go", True, True, False, True),      # Go with add-on: eligible
    ("N009", True, "Pro", False, True, False, True),    # broken but eligible
    ("N010", True, "Plus", False, True, True, True),    # already enabled
    ("N011", False, "Pro", False, True, False, True),   # suspended
    ("N012", True, "Plus", False, True, False, False),  # eligible, owner not verified
]


class TelecomDomain(Domain):
    id = "telecom"
    display_name = "Nimbus Mobile"
    company = "Nimbus Mobile"
    prefix = "N"
    noun = "line"
    tools = TOOLS
    profile_tool = "lines.get_profile"
    entitlement_tool = "lines.check_entitlement"
    default_feature = "roaming"
    prereq_fields = ("active", "upgraded", "roaming_enabled")
    degraded_field = "roaming_service_degraded"
    default_intent = "roaming_lost_after_upgrade"
    vocabulary = {"internet": "data", "signal": "data", "web": "data", "4g": "data", "5g": "data", "lte": "data", "browsing": "data",
                  "whatsapp": "data", "maps": "data", "loads": "stuck", "load": "stuck", "rejects": "stuck", "denied": "stuck",
                  "landed": "abroad", "landing": "abroad", "arrived": "abroad", "flight": "abroad", "airport": "abroad", "border": "abroad",
                  "europe": "abroad", "spain": "abroad", "italy": "abroad", "france": "abroad", "germany": "abroad", "portugal": "abroad",
                  "greece": "abroad", "uk": "abroad", "london": "abroad", "paris": "abroad", "usa": "abroad", "mexico": "abroad",
                  "canada": "abroad", "japan": "abroad", "india": "abroad", "thailand": "abroad", "australia": "abroad", "dubai": "abroad",
                  "turkey": "abroad", "ireland": "abroad", "netherlands": "abroad", "switzerland": "abroad"}
    intent_examples = ("no data roaming abroad after the Core Network Upgrade 5, RM-100",
                       "mobile data not working while travelling overseas since the network upgrade",
                       "roaming lost or disabled on the line after CNU-5")
    escalation_options = ["email ticket to care@nimbus-mobile.example", "phone or callback (555) 010-0177"]
    already_ok_message = "Roaming is already provisioned on this line and the gateway test passes. No change was needed."

    def seed_rows(self) -> list:
        return [{"id": i, "active": a, "plan": p, "roaming_addon": ad, "upgraded": u, "roaming_enabled": r, "owner_verified": o,
                 "roaming_service_degraded": False, "credits": []}
                for i, a, p, ad, u, r, o in SEED_LINES]

    def public_profile(self, acc: dict) -> dict:
        return {k: acc.get(k) for k in ("active", "plan", "roaming_addon", "upgraded", "roaming_enabled", "owner_verified")}

    def _plan_has_roaming(self, acc: dict) -> bool:
        return acc.get("plan") in ROAMING_PLANS or (acc.get("plan") == "Go" and bool(acc.get("roaming_addon")))

    def entitlement(self, acc: dict, feature: str) -> dict:
        if feature != "roaming":
            return {"eligible": False, "reason": f"unknown feature '{feature}'"}
        if not acc.get("active"):
            return {"eligible": False, "reason": "line suspended (RM-300)"}
        if not self._plan_has_roaming(acc):
            return {"eligible": False, "reason": f"plan {acc.get('plan')} has no roaming add-on (RM-200); Plus, Pro or Go with the roaming add-on only"}
        if acc.get("roaming_enabled") is None:
            return {"eligible": False, "reason": "roaming provisioning state unknown; needs human review"}
        return {"eligible": True, "reason": f"plan {acc.get('plan')}" + (" with roaming add-on" if acc.get("roaming_addon") else "") + " on an active line"}

    def invoke(self, store: Store, tenant_id: str, tool_id: str, params: dict, acc: Optional[dict], before: Optional[dict]) -> dict:
        if tool_id == "lines.get_profile":
            return ok_result(before, before, before)
        if tool_id == "lines.check_entitlement":
            return ok_result(self.entitlement(acc, params.get("feature", "")), before, before)
        if tool_id == "lines.enable_roaming":
            ent = self.entitlement(acc, "roaming")
            if not ent["eligible"]:
                return failed_result({"enabled": False, "reason": ent["reason"]}, before)
            if not acc.get("upgraded"):
                return failed_result({"enabled": False, "reason": "line is not on the upgraded core network (CNU-5); this remedy only applies after the upgrade"}, before)
            if acc.get("roaming_enabled") is True:
                return ok_result({"enabled": True, "changed": False, "reason": "already enabled"}, before, before)
            acc["roaming_enabled"] = True
            acc["updated_at"] = now_iso()
            store.put("account", acc)
            return ok_result({"enabled": True, "changed": True}, before, self.public_profile(acc))
        if tool_id == "network.test_roaming":
            if not acc.get("active"):
                out = {"roaming_ok": False, "error_code": "RM-300"}
            elif not self._plan_has_roaming(acc):
                out = {"roaming_ok": False, "error_code": "RM-200"}
            elif acc.get("roaming_enabled") is not True:
                out = {"roaming_ok": False, "error_code": "RM-100"}
            elif acc.get("roaming_service_degraded"):
                out = {"roaming_ok": False, "error_code": "RM-500"}
            else:
                out = {"roaming_ok": True, "error_code": None}
            return ok_result(out, before, before)
        if tool_id == "billing.issue_credit":
            try:
                amount = float(params.get("amount"))
            except (TypeError, ValueError):
                raise ApiError(400, "BAD_AMOUNT", "amount must be a number")
            if amount <= 0 or amount > 500:
                raise ApiError(400, "BAD_AMOUNT", "amount must be between 0 and 500")
            acc.setdefault("credits", []).append({"amount": amount, "at": now_iso()})
            acc["updated_at"] = now_iso()
            store.put("account", acc)
            return ok_result({"credited": True, "amount": amount, "credits": len(acc["credits"])}, before, self.public_profile(acc))
        if tool_id == "account.change_owner":
            new_owner = str(params.get("new_owner") or "").strip()
            if not new_owner:
                raise ApiError(400, "BAD_OWNER", "new_owner is required")
            acc["owner"] = new_owner
            acc["owner_verified"] = True
            acc["updated_at"] = now_iso()
            store.put("account", acc)
            return ok_result({"changed": True, "owner": new_owner}, before, self.public_profile(acc))
        raise ApiError(400, "TOOL_NOT_IMPLEMENTED", tool_id)

    def status(self, acc: dict) -> dict:
        p = self.public_profile(acc)
        if not p["active"]:
            summary = "Line suspended: calls, data and roaming are disabled (RM-300)."
        elif not self._plan_has_roaming(acc):
            summary = f"Active {p['plan']} line without the roaming add-on: roaming is not included in the plan (RM-200)."
        elif p["roaming_enabled"] is True:
            summary = f"Active {p['plan']} line, roaming provisioned and working."
        elif p["roaming_enabled"] is None:
            summary = "Active line but the roaming provisioning state is unknown; a specialist must review it."
        else:
            summary = f"Active {p['plan']} line entitled to roaming, but roaming is not provisioned (RM-100)" + (" after the CNU-5 core network upgrade." if p["upgraded"] else ".")
        return {"account_id": acc["id"], **p, "summary": summary}

    def draft_prerequisites(self) -> list:
        return [{"field": "active", "op": "==", "value": True}, {"field": "upgraded", "op": "==", "value": True},
                {"tool": "lines.check_entitlement", "params": {"feature": "roaming"}, "expect": {"eligible": True}}]
