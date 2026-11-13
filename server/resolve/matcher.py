"""Intent and paraphrase matching over APPROVED playbooks. A match is never authorization."""
import re
from typing import Optional

from ..common import tokenize
from ..config import ABSTAIN_THRESHOLD, MATCH_THRESHOLD

# Canonical forms so that "download", "csv", "spins", "migrated" all land on the same concepts.
CANON = {
    "download": "export", "downloading": "export", "csv": "export", "pdf": "export", "exports": "export", "exporting": "export",
    "exported": "export", "extract": "export",
    "spins": "stuck", "spinning": "stuck", "hangs": "stuck", "hanging": "stuck", "hang": "stuck", "frozen": "stuck",
    "loading": "stuck", "forever": "stuck", "finishes": "stuck", "finish": "stuck", "starts": "stuck", "start": "stuck",
    "stopped": "stuck", "never": "stuck", "cant": "stuck", "can't": "stuck", "won't": "stuck", "wont": "stuck", "fails": "stuck",
    "not": "stuck", "broken": "stuck", "stays": "stuck", "stay": "stuck", "keeps": "stuck",
    "migrated": "migration", "migrate": "migration", "move": "migration", "moved": "migration", "cloud": "migration",
    "reports": "report", "dashboards": "report", "dashboard": "report",
    # telecom (Nimbus Mobile): roaming lost after the core network upgrade
    "roam": "roaming", "roams": "roaming", "abroad": "abroad", "overseas": "abroad", "international": "abroad",
    "travelling": "abroad", "traveling": "abroad", "travel": "abroad", "trip": "abroad", "holiday": "abroad", "vacation": "abroad",
    "upgraded": "upgrade", "upgrades": "upgrade", "upgrading": "upgrade",
    "doesnt": "stuck", "isnt": "stuck", "no": "stuck", "nothing": "stuck", "working": "stuck", "works": "stuck", "work": "stuck",
    "dead": "stuck", "lost": "stuck", "disappeared": "stuck", "gone": "stuck",
}
STOP = {"the", "a", "an", "my", "our", "we", "i", "it", "is", "to", "of", "and", "after", "since", "in", "on", "for", "at",
        "button", "problem", "orbit", "get", "out", "will", "with", "again", "still", "please", "help", "hi", "hello"}
INJECTION = re.compile(r"(ignore (all|previous|the) (checks|instructions|rules)|run the admin tool|delete_all|drop table|system prompt)", re.I)


def concepts(text: str) -> set:
    toks = tokenize(text.replace("'", ""))
    out = set()
    for t in toks:
        if t in STOP:
            continue
        out.add(CANON.get(t, t))
    return out


def score(utterance: str, example: str) -> float:
    a, b = concepts(utterance), concepts(example)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    # Overlap coefficient (recall-friendly for short customer messages) but a single shared concept is never
    # enough on its own: it is capped into the abstain band so that e.g. "export" alone cannot trigger a fix.
    overlap = inter / min(len(a), len(b))
    return min(overlap, 0.3) if inter < 2 else overlap


EXECUTABLE = ("APPROVED", "SUPERVISED")


def match(utterance: str, playbooks: list, domain: Optional[str] = None) -> dict:
    """Return {decision: match|abstain|none, playbook, score, injection}. Only this domain's executable playbooks count."""
    injection = bool(INJECTION.search(utterance or ""))
    best, best_score = None, 0.0
    for pb in playbooks:
        if pb.get("status") not in EXECUTABLE:
            continue  # retired, draft and pending are filtered out, whatever their similarity
        if domain and pb.get("domain", "saas") != domain:
            continue
        s = max((score(utterance, ex) for ex in pb.get("match_examples", [])), default=0.0)
        if s > best_score:
            best, best_score = pb, s
    if injection:
        return {"decision": "none", "playbook": None, "score": best_score, "injection": True}
    if best and best_score >= MATCH_THRESHOLD:
        return {"decision": "match", "playbook": best, "score": round(best_score, 3), "injection": False}
    if best and best_score >= ABSTAIN_THRESHOLD:
        return {"decision": "abstain", "playbook": best, "score": round(best_score, 3), "injection": False}
    return {"decision": "none", "playbook": None, "score": round(best_score, 3), "injection": False}
