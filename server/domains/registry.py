"""Registry of domains and the rules that pick one for a request.

Resolution order: an explicit "domain" field or X-Domain header, else the account id prefix (C -> saas, N -> telecom),
else the default (saas). Tool ids are unique across domains except `cases.escalate`, which every domain shares.
"""
from typing import Optional

from ..common import ApiError
from .base import Domain
from .saas import SaasDomain
from .telecom import TelecomDomain

DOMAINS: dict = {d.id: d for d in (SaasDomain(), TelecomDomain())}
DEFAULT_DOMAIN = "saas"


def get_domain(domain_id: Optional[str]) -> Domain:
    d = DOMAINS.get((domain_id or "").strip().lower())
    if not d:
        raise ApiError(400, "UNKNOWN_DOMAIN", f"Unknown domain '{domain_id}'; one of {sorted(DOMAINS)}")
    return d


def domain_for_account_id(account_id: Optional[str]) -> Optional[Domain]:
    if not account_id:
        return None
    first = account_id.strip()[:1].upper()
    for d in DOMAINS.values():
        if d.prefix == first:
            return d
    return None


def domain_of(acc: dict) -> Domain:
    """The domain an account record belongs to (stored field, else inferred from its id)."""
    if acc.get("domain") in DOMAINS:
        return DOMAINS[acc["domain"]]
    return domain_for_account_id(acc.get("id")) or DOMAINS[DEFAULT_DOMAIN]


def resolve_domain(explicit: Optional[str] = None, header: Optional[str] = None, account_id: Optional[str] = None) -> Domain:
    if explicit:
        return get_domain(explicit)
    if header:
        return get_domain(header)
    return domain_for_account_id(account_id) or DOMAINS[DEFAULT_DOMAIN]


def domains_for_tool(tool_id: str) -> list:
    return [d for d in DOMAINS.values() if tool_id in d.tools]


def all_tools() -> dict:
    """Merged allowlist across domains. Shared ids (cases.escalate) have an identical spec in every domain."""
    merged: dict = {}
    for d in DOMAINS.values():
        for t, spec in d.tools.items():
            merged.setdefault(t, spec)
    return merged
