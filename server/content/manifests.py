"""Knowledge-base manifests and content buckets.

Each domain ships knowledge/manifest-<domain>.json listing its documents with a bucket:
  public      customer-facing help articles; body served to anyone
  internal    specialist runbooks; body served with a valid API key and fed to the LLM drafter
  restricted  human-only material; the entry is listed but the body is never served by the API
A missing manifest is logged and treated as "no documents"; it never stops the service.
"""
import json
import logging
import os
from typing import Optional

from .. import config
from ..domains import DOMAINS

log = logging.getLogger("resolveloop.content")
BUCKETS = ("public", "internal", "restricted")

_cache: dict = {"dir": None, "manifests": {}}


def knowledge_dir() -> str:
    return os.path.abspath(config.KNOWLEDGE_DIR)


def load(force: bool = False) -> dict:
    """Load manifest-<domain>.json for every registered domain (cached per knowledge dir)."""
    kdir = knowledge_dir()
    if not force and _cache["dir"] == kdir:
        return _cache["manifests"]
    manifests = {}
    for d in DOMAINS:
        path = os.path.join(kdir, f"manifest-{d}.json")
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
            docs = [e for e in m.get("documents", []) if isinstance(e, dict) and e.get("id")]
            for e in docs:
                e.setdefault("bucket", "public")
                e["domain"] = d
            m["documents"] = docs
            manifests[d] = m
        except FileNotFoundError:
            log.warning("knowledge manifest missing for domain %s (%s): treating as no documents", d, path)
            manifests[d] = {"domain": d, "documents": []}
        except (OSError, ValueError) as e:
            log.error("knowledge manifest unreadable for domain %s: %s", d, e)
            manifests[d] = {"domain": d, "documents": [], "error": str(e)}
    _cache.update(dir=kdir, manifests=manifests)
    return manifests


def reload() -> dict:
    return load(force=True)


def documents(domain: Optional[str] = None, bucket: Optional[str] = None) -> list:
    out = []
    for d, m in load().items():
        if domain and d != domain:
            continue
        for e in m["documents"]:
            if bucket and e.get("bucket") != bucket:
                continue
            out.append(e)
    return out


def find(doc_id: str, domain: Optional[str] = None) -> Optional[dict]:
    for e in documents(domain):
        if e["id"] == doc_id:
            return e
    return None


def counts(domain: str) -> dict:
    c = {b: 0 for b in BUCKETS}
    for e in documents(domain):
        c[e.get("bucket", "public")] = c.get(e.get("bucket", "public"), 0) + 1
    return c


def _safe_path(rel: Optional[str]) -> Optional[str]:
    """Resolve a manifest-relative path and refuse anything that escapes the knowledge directory."""
    if not rel:
        return None
    root = knowledge_dir()
    full = os.path.abspath(os.path.join(root, rel))
    return full if full.startswith(root + os.sep) else None


def body(entry: dict) -> Optional[str]:
    path = _safe_path(entry.get("file"))
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def pdf_path(domain: str, name: str) -> Optional[str]:
    """Locate a domain PDF by file name via the manifest, then by convention under knowledge/."""
    for e in documents(domain):
        p = _safe_path(e.get("pdf"))
        if p and os.path.basename(p) == name and os.path.isfile(p):
            return p
    for rel in (os.path.join("pdf", domain, name), os.path.join(domain, "pdf", name), os.path.join(domain, name)):
        p = _safe_path(rel)
        if p and os.path.isfile(p):
            return p
    return None


def internal_runbooks(domain: str) -> list:
    """[(entry, text)] for the domain's INTERNAL bucket only. Restricted material never leaves the human desk."""
    out = []
    for e in documents(domain, "internal"):
        text = body(e)
        if text:
            out.append((e, text))
    return out
