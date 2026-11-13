"""Domain "ithelpdesk": Northgate University IT. User accounts (U001..U012) lose VPN access after the single-sign-on
migration (SSO 2 cutover) because their access group was not re-synced.

Mirror of the telecom story: an active, entitled (student/staff/faculty), migrated account has vpn_group_synced=False
and the fix is a low-risk group re-sync. Two HIGH-risk tools (password reset, owner e-mail change) exist so the
human-only gate has teeth. Error codes: AC-100 group not synced, AC-200 role not entitled to VPN, AC-300 account
suspended, AC-500 VPN gateway fault.
"""
from typing import Optional

from ..common import ApiError, now_iso
from ..db import Store
from .base import ESCALATE_TOOL, Domain, failed_result, ok_result

VPN_ROLES = ("student", "staff", "faculty")

TOOLS: dict = {
    "users.get_profile": {"kind": "read", "risk": "low", "params": ["account_id"], "description": "Read the synthetic user account (account_id is the user id)"},
    "access.check_entitlement": {"kind": "read", "risk": "low", "params": ["account_id", "feature"], "description": "Is the account entitled to a feature (vpn) by role, status and SSO migration?"},
    "access.resync_group": {"kind": "mutation", "risk": "low", "params": ["account_id"], "description": "Re-sync the VPN access group for an active, entitled, migrated account"},
    "access.test_vpn_login": {"kind": "verify", "risk": "low", "ok_key": "vpn_ok", "params": ["account_id"], "description": "Attempt a test VPN login for the account and report whether it succeeds"},
    "identity.reset_password": {"kind": "mutation", "risk": "high", "params": ["account_id"], "description": "Reset the account password (human-only, identity-sensitive)"},
    "identity.change_owner_email": {"kind": "mutation", "risk": "high", "params": ["account_id", "new_email"], "description": "Change the recovery e-mail that owns the account (human-only)"},
    "cases.escalate": ESCALATE_TOOL,
}

SEED_USERS = [
    # id, active, role, migrated, vpn_group_synced, owner_verified
    ("U001", True, "staff", True, False, True),     # broken but eligible
    ("U002", True, "student", True, False, True),   # broken but eligible (paraphrase target)
    ("U003", False, "staff", True, False, True),    # suspended (AC-300)
    ("U004", True, "guest", True, False, True),     # guest role: no VPN (AC-200)
    ("U005", True, "faculty", True, True, True),    # already synced
    ("U006", True, "staff", False, False, True),    # not migrated to SSO 2 yet
    ("U007", True, "student", True, None, True),    # sync state unknown
    ("U008", True, "faculty", True, False, True),   # broken but eligible
    ("U009", True, "staff", True, False, True),     # broken but eligible
    ("U010", True, "student", True, True, True),    # already synced
    ("U011", False, "student", True, False, True),  # suspended
    ("U012", True, "faculty", True, False, False),  # eligible, owner not verified
]


class ItHelpdeskDomain(Domain):
    id = "ithelpdesk"
    display_name = "Northgate IT Helpdesk"
    company = "Northgate University IT"
    prefix = "U"
    noun = "user"
    tools = TOOLS
    profile_tool = "users.get_profile"
    entitlement_tool = "access.check_entitlement"
    default_feature = "vpn"
    # `role` is deliberately not a profile prerequisite: a fix learned on a staff account must apply to students and
    # faculty too. access.check_entitlement carries the role check (AC-200) instead.
    prereq_fields = ("active", "migrated", "vpn_group_synced")
    degraded_field = "vpn_service_degraded"
    default_intent = "vpn_access_lost_after_sso2"
    vocabulary = {"portal": "sso", "okta": "sso", "credentials": "sso", "mfa": "sso", "duo": "sso", "password": "sso",
                  "rejects": "stuck", "rejected": "stuck", "denied": "stuck", "refused": "stuck", "blocked": "stuck", "kicked": "stuck",
                  "anyconnect": "vpn", "globalprotect": "vpn", "wireguard": "vpn", "campus": "vpn", "offsite": "vpn", "home": "vpn"}
    intent_examples = ("VPN access lost after the SSO 2 sign-on cutover, AC-100",
                       "cannot connect to the campus VPN since the single sign-on migration",
                       "VPN login rejected, access group not synced")
    escalation_options = ["email ticket to helpdesk@northgate-u.example", "phone or callback (555) 010-0466"]
    already_ok_message = "The VPN access group is already synced for this account and a test VPN login succeeds. No change was needed."

    def seed_rows(self) -> list:
        return [{"id": i, "active": a, "role": r, "migrated": m, "vpn_group_synced": s, "owner_verified": o,
                 "vpn_service_degraded": False, "password_resets": 0}
                for i, a, r, m, s, o in SEED_USERS]

    def public_profile(self, acc: dict) -> dict:
        return {k: acc.get(k) for k in ("active", "role", "migrated", "vpn_group_synced", "owner_verified")}

    def entitlement(self, acc: dict, feature: str) -> dict:
        if feature != "vpn":
            return {"eligible": False, "reason": f"unknown feature '{feature}'"}
        if not acc.get("active"):
            return {"eligible": False, "reason": "account suspended (AC-300)"}
        if acc.get("role") not in VPN_ROLES:
            return {"eligible": False, "reason": f"role '{acc.get('role')}' is not entitled to VPN (AC-200); students, staff and faculty only"}
        if not acc.get("migrated"):
            return {"eligible": False, "reason": "account still on the legacy sign-on; its VPN group is managed by the old flow and this remedy does not apply"}
        if acc.get("vpn_group_synced") is None:
            return {"eligible": False, "reason": "VPN access-group state unknown; needs human review"}
        return {"eligible": True, "reason": f"active {acc.get('role')} account on SSO 2"}

    def invoke(self, store: Store, tenant_id: str, tool_id: str, params: dict, acc: Optional[dict], before: Optional[dict]) -> dict:
        if tool_id == "users.get_profile":
            return ok_result(before, before, before)
        if tool_id == "access.check_entitlement":
            return ok_result(self.entitlement(acc, params.get("feature", "")), before, before)
        if tool_id == "access.resync_group":
            ent = self.entitlement(acc, "vpn")
            if not ent["eligible"]:
                return failed_result({"synced": False, "reason": ent["reason"]}, before)
            if not acc.get("migrated"):
                return failed_result({"synced": False, "reason": "account is not on SSO 2; this remedy only applies after the sign-on cutover"}, before)
            if acc.get("vpn_group_synced") is True:
                return ok_result({"synced": True, "changed": False, "reason": "already synced"}, before, before)
            acc["vpn_group_synced"] = True
            acc["updated_at"] = now_iso()
            store.put("account", acc)
            return ok_result({"synced": True, "changed": True}, before, self.public_profile(acc))
        if tool_id == "access.test_vpn_login":
            if not acc.get("active"):
                out = {"vpn_ok": False, "error_code": "AC-300"}
            elif acc.get("role") not in VPN_ROLES:
                out = {"vpn_ok": False, "error_code": "AC-200"}
            elif acc.get("vpn_group_synced") is not True:
                out = {"vpn_ok": False, "error_code": "AC-100"}
            elif acc.get("vpn_service_degraded"):
                out = {"vpn_ok": False, "error_code": "AC-500"}
            else:
                out = {"vpn_ok": True, "error_code": None}
            return ok_result(out, before, before)
        if tool_id == "identity.reset_password":
            acc["password_resets"] = int(acc.get("password_resets") or 0) + 1
            acc["password_reset_at"] = now_iso()
            acc["updated_at"] = now_iso()
            store.put("account", acc)
            # The temporary password goes to the recovery address on file; it is never returned by the API.
            return ok_result({"reset": True, "delivery": "temporary password sent to the recovery e-mail on file", "resets": acc["password_resets"]}, before, self.public_profile(acc))
        if tool_id == "identity.change_owner_email":
            new_email = str(params.get("new_email") or "").strip()
            if not new_email or "@" not in new_email:
                raise ApiError(400, "BAD_EMAIL", "new_email must be an e-mail address")
            acc["owner_email"] = new_email
            acc["updated_at"] = now_iso()
            store.put("account", acc)
            return ok_result({"changed": True}, before, self.public_profile(acc))
        raise ApiError(400, "TOOL_NOT_IMPLEMENTED", tool_id)

    def status(self, acc: dict) -> dict:
        p = self.public_profile(acc)
        if not p["active"]:
            summary = "Account suspended: sign-in, e-mail and VPN are disabled (AC-300)."
        elif p["role"] not in VPN_ROLES:
            summary = f"Active {p['role']} account: VPN is not included for this role (AC-200)."
        elif p["vpn_group_synced"] is True:
            summary = f"Active {p['role']} account, VPN access group synced and VPN login works."
        elif p["vpn_group_synced"] is None:
            summary = "Active account but the VPN access-group state is unknown; a specialist must review it."
        else:
            summary = f"Active {p['role']} account entitled to VPN, but the access group is not synced (AC-100)" + (" after the SSO 2 cutover." if p["migrated"] else ".")
        return {"account_id": acc["id"], **p, "summary": summary}

    def draft_prerequisites(self) -> list:
        return [{"field": "active", "op": "==", "value": True}, {"field": "migrated", "op": "==", "value": True},
                {"tool": "access.check_entitlement", "params": {"feature": "vpn"}, "expect": {"eligible": True}}]
