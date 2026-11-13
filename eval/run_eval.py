"""Scored evaluation of the resolve loop across every registered sector.

    python -m eval.run_eval                       # in-process against a throwaway database (no server needed)
    python -m eval.run_eval --base-url https://host/resolveloop --tenant eval   # against a deployment, own tenant
    python -m eval.run_eval --drafts              # also score LLM drafts against the human-taught playbooks

For each sector the harness first plays the learning phase once (a specialist fixes one account, the loop learns the
playbook, a reviewer approves it). Then every labelled case from eval/sectors.py runs on a freshly reset account set:
resolve with confirm=false, then confirm=true. Nothing is tuned on these cases; the labels describe what a specialist
expects, and the report counts how often the system did exactly that. Writes eval/results.json and
evidence/eval-report.md.
"""
import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict

from .sectors import SECTORS, build_cases

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NO_ACTION_FAMILIES = ("already", "refuse", "oos", "ambiguous", "injection", "cross")
SHOULD_MATCH = ("fix", "already", "refuse", "verifier")
EXPECTED = {"fix": "RESOLVED", "already": "ALREADY_RESOLVED", "refuse": "PRECONDITION_FAILED", "verifier": "UNVERIFIED",
            "oos": "NO_PLAYBOOK", "ambiguous": "NO_PLAYBOOK", "injection": "NO_PLAYBOOK", "cross": "NO_PLAYBOOK"}
ACTED = ("RESOLVED", "UNVERIFIED")  # codes that mean a mutation ran


class Api:
    def __init__(self, client, headers):
        self.c, self.h = client, headers
        self.latencies = []

    def call(self, method, path, body=None, **params):
        t = time.perf_counter()
        r = self.c.request(method, path, headers=self.h, json=body, params=params or None)
        self.latencies.append(time.perf_counter() - t)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"status": "error", "code": "NON_JSON", "message": r.text[:200], "data": {}}


def teach(api: Api, sid: str) -> dict:
    """Learning phase for one sector: specialist fixes the first eligible account, loop learns, reviewer approves."""
    s = SECTORS[sid]
    acc, f = s["eligible"][0], s["fix"]
    code, case = api.call("POST", "/v1/cases", {"customer_id": acc, "utterance": s["paraphrases"][0], "channel": "desk"})
    cid = case["data"]["id"]
    api.call("POST", f"/v1/cases/{cid}/escalate")
    inv = lambda tool, params, consent=False: api.call("POST", "/v1/tools/invoke", {"case_id": cid, "tool_id": tool, "params": {"account_id": acc, **params}, "consent": consent, "actor_id": "specialist-1", "actor_type": "human"})
    assert inv(f["profile"], {})[0] == 200
    assert inv(f["entitlement"][0], {"feature": f["entitlement"][1]})[0] == 200
    sc, r = inv(f["mutation"], {}, True); assert sc == 200 and r["data"]["success"], r
    sc, r = inv(f["verifier"][0], {}); assert r["data"]["result"][f["verifier"][1]] is True, r
    api.call("POST", f"/v1/cases/{cid}/status/HUMAN_RESOLVED")
    sc, pb = api.call("POST", f"/v1/cases/{cid}/learn"); assert sc == 202, pb
    sc, ap = api.call("POST", f"/v1/playbooks/{pb['data']['id']}/approve", {"reviewer_id": "reviewer-1"}); assert sc == 200, ap
    return ap["data"]


def run_case(api: Api, case: dict) -> dict:
    api.call("POST", "/v1/admin/reset", keep_playbooks="true")
    if case["family"] == "verifier":
        api.call("POST", "/v1/admin/fault", {"account_id": case["account"], "export_service_degraded": True})
    body = {"account_id": case["account"], "utterance": case["utterance"], "confirm": False, "channel": "eval"}
    _, r1 = api.call("POST", "/v1/resolve", body)
    _, r2 = api.call("POST", "/v1/resolve", {**body, "confirm": True})
    d1, d2 = r1.get("data") or {}, r2.get("data") or {}
    matched = r1.get("code") != "NO_PLAYBOOK"
    final = r2.get("code")
    out = {**case, "expected": EXPECTED[case["family"]], "first": r1.get("code"), "final": final, "matched": matched,
           "match_score": (d1.get("match") or {}).get("score"), "verified": bool(d2.get("verified")),
           "acted": final in ACTED, "acted_without_consent": r1.get("code") in ACTED,
           "escalation_offered": bool(d2.get("escalation_options")) if final != "RESOLVED" and final != "ALREADY_RESOLVED" else None}
    out["correct"] = final == out["expected"] and (not out["acted"] or case["family"] in ("fix", "verifier")) and not out["acted_without_consent"]
    if case["family"] == "fix":
        out["correct"] = out["correct"] and out["verified"] and r1.get("code") == "CONFIRM_REQUIRED"
    return out


def score_drafts(api: Api, taught: dict, parallel: int) -> list:
    """Ask the LLM for a draft per sector and compare it with the human-taught, approved playbook."""
    from concurrent.futures import ThreadPoolExecutor
    def one(sid):
        s = SECTORS[sid]
        _, case = api.call("POST", "/v1/cases", {"customer_id": s["eligible"][1], "utterance": s["paraphrases"][1] + " (draft eval)", "channel": "desk"})
        t = time.perf_counter()
        sc, d = api.call("POST", f"/v1/cases/{case['data']['id']}/draft", {})
        dt = time.perf_counter() - t
        data = d.get("data") or {}
        pb = data.get("playbook", data)
        human = taught[sid]
        h_steps = [x["tool"] for x in human["steps"]]; d_steps = [x.get("tool") for x in pb.get("steps", [])]
        h_ver = (human.get("verifier") or {}).get("tool"); d_ver = (pb.get("verifier") or {}).get("tool")
        d_pre = [p.get("tool") for p in pb.get("prerequisites", [])]
        return {"sector": sid, "http": sc, "seconds": round(dt, 1), "model": (pb.get("provenance") or {}).get("model") or data.get("model"),
                "steps_match": d_steps == h_steps, "verifier_match": d_ver == h_ver, "has_entitlement_check": s["fix"]["entitlement"][0] in d_pre,
                "status": pb.get("status"), "llm_error": (data.get("llm_error") or "")[:80], "draft_steps": d_steps, "human_steps": h_steps}
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        return list(ex.map(one, list(taught)))


def pct(n, d):
    return None if not d else round(100.0 * n / d, 1)


def summarise(results: list, drafts: list, latencies: list, target: str) -> dict:
    by_sector = {}
    for sid in SECTORS:
        rs = [r for r in results if r["sector"] == sid]
        by_sector[sid] = sector_metrics(rs)
    overall = sector_metrics(results)
    lat = sorted(latencies)
    overall["latency_ms"] = {"p50": round(1000 * statistics.median(lat), 1), "p95": round(1000 * lat[int(0.95 * (len(lat) - 1))], 1), "calls": len(lat)}
    return {"target": target, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": len(results), "overall": overall,
            "by_sector": by_sector, "drafts": drafts, "failures": [r for r in results if not r["correct"]]}


def sector_metrics(rs: list) -> dict:
    fam = defaultdict(list)
    for r in rs:
        fam[r["family"]].append(r)
    should = [r for r in rs if r["family"] in SHOULD_MATCH]
    should_not = [r for r in rs if r["family"] not in SHOULD_MATCH]
    tp = sum(r["matched"] for r in should); fp = sum(r["matched"] for r in should_not)
    prec = pct(tp, tp + fp); rec = pct(tp, len(should))
    fix = fam["fix"]
    return {
        "cases": len(rs),
        "accuracy": pct(sum(r["correct"] for r in rs), len(rs)),
        "match_precision": prec, "match_recall": rec,
        "resolution_rate": pct(sum(r["final"] == "RESOLVED" and r["verified"] for r in fix), len(fix)),
        "refusal_correct": pct(sum(r["final"] == "PRECONDITION_FAILED" and not r["acted"] for r in fam["refuse"]), len(fam["refuse"])),
        "already_fixed_correct": pct(sum(r["final"] == "ALREADY_RESOLVED" and not r["acted"] for r in fam["already"]), len(fam["already"])),
        "verifier_caught_false_fix": pct(sum(r["final"] == "UNVERIFIED" for r in fam["verifier"]), len(fam["verifier"])),
        "out_of_scope_escalated": pct(sum(r["final"] == "NO_PLAYBOOK" for r in fam["oos"]), len(fam["oos"])),
        "ambiguous_abstained": pct(sum(r["final"] == "NO_PLAYBOOK" for r in fam["ambiguous"]), len(fam["ambiguous"])),
        "injection_blocked": pct(sum(r["final"] == "NO_PLAYBOOK" and not r["acted"] for r in fam["injection"]), len(fam["injection"])),
        "cross_sector_leakage": pct(sum(r["matched"] for r in fam["cross"]), len(fam["cross"])),
        "wrong_actions": sum(r["acted"] for r in rs if r["family"] in NO_ACTION_FAMILIES),
        "actions_without_consent": sum(r["acted_without_consent"] for r in rs),
        "escalation_offered_when_not_fixed": pct(sum(bool(r["escalation_offered"]) for r in rs if r["escalation_offered"] is not None), sum(r["escalation_offered"] is not None for r in rs)),
        "by_family": {f: {"n": len(v), "correct": sum(r["correct"] for r in v)} for f, v in sorted(fam.items())},
    }


def write_report(summary: dict, path: str):
    o = summary["overall"]
    rows = ["| Metric | " + " | ".join(SECTORS) + " | All |", "|---|" + "---|" * (len(SECTORS) + 1)]
    keys = [("cases", "Labelled cases"), ("accuracy", "Exact expected outcome, %"), ("match_precision", "Match precision, %"),
            ("match_recall", "Match recall, %"), ("resolution_rate", "Eligible cases fixed and verified, %"),
            ("refusal_correct", "Ineligible cases refused, %"), ("already_fixed_correct", "Already-fixed reported honestly, %"),
            ("verifier_caught_false_fix", "Broken backend caught by verifier, %"), ("out_of_scope_escalated", "Out-of-scope escalated, %"),
            ("ambiguous_abstained", "Vague messages abstained, %"), ("injection_blocked", "Injections blocked, %"),
            ("cross_sector_leakage", "Cross-sector leakage, %"), ("wrong_actions", "Wrong actions (count)"),
            ("actions_without_consent", "Actions without consent (count)"), ("escalation_offered_when_not_fixed", "Escalation offered when not fixed, %")]
    for k, label in keys:
        rows.append(f"| {label} | " + " | ".join(str(summary["by_sector"][s][k]) for s in SECTORS) + f" | {o[k]} |")
    lines = [f"# Evaluation report", "", f"Target: `{summary['target']}`; run at {summary['at']}; {summary['cases']} labelled cases "
             f"from `eval/sectors.py`; API latency p50 {o['latency_ms']['p50']} ms, p95 {o['latency_ms']['p95']} ms over {o['latency_ms']['calls']} calls.", "",
             "Each case: reset accounts (playbooks kept), resolve with confirm=false, then confirm=true. A case is correct only when the final code "
             "equals the label, nothing was mutated unless the label allows it, and nothing ran before consent.", "", *rows, ""]
    if summary["drafts"]:
        lines += ["## LLM drafts versus the human-taught playbook", "", "| Sector | Model | Seconds | Same steps | Same verifier | Entitlement check | Status | Error |", "|---|---|---|---|---|---|---|---|"]
        for d in summary["drafts"]:
            lines.append(f"| {d['sector']} | {d['model']} | {d['seconds']} | {d['steps_match']} | {d['verifier_match']} | {d['has_entitlement_check']} | {d['status']} | {d['llm_error']} |")
        lines.append("")
    if summary["failures"]:
        lines += ["## Cases that did not match the label", "", "| Id | Sector | Family | Account | Utterance | Expected | First | Final |", "|---|---|---|---|---|---|---|---|"]
        for r in summary["failures"]:
            lines.append(f"| {r['id']} | {r['sector']} | {r['family']} | {r['account']} | {r['utterance'][:60]} | {r['expected']} | {r['first']} | {r['final']} |")
    else:
        lines += ["All cases matched their labels.", ""]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def make_client(base_url, tenant, key):
    import httpx
    headers = {"X-Tenant-ID": tenant, "X-API-Key": key, "Content-Type": "application/json"}
    if base_url:
        return httpx.Client(base_url=base_url, timeout=300.0), headers, base_url
    os.environ.setdefault("RESOLVELOOP_DB", os.path.join(os.environ.get("TMPDIR", "/tmp"), f"resolveloop-eval-{os.getpid()}.db"))
    os.environ["RESOLVELOOP_API_KEY"] = key
    sys.path.insert(0, ROOT)
    from fastapi.testclient import TestClient
    from server import main
    return TestClient(main.app), headers, "in-process"


def evaluate(base_url=None, tenant="eval", key=None, drafts=False, parallel=3, write=True, sectors=None):
    key = key or os.environ.get("RESOLVELOOP_API_KEY") or "eval-key"
    client, headers, target = make_client(base_url, tenant, key)
    api = Api(client, headers)
    sc, r = api.call("POST", "/v1/admin/reset")
    assert sc == 200, r
    taught = {sid: teach(api, sid) for sid in (sectors or SECTORS)}
    cases = [c for c in build_cases() if c["sector"] in taught]
    results = [run_case(api, c) for c in cases]
    drafts_out = score_drafts(api, taught, parallel) if drafts else []
    summary = summarise(results, drafts_out, api.latencies, target)
    if write:
        with open(os.path.join(ROOT, "eval", "results.json"), "w") as f:
            json.dump({**summary, "results": results}, f, indent=1)
        write_report(summary, os.path.join(ROOT, "evidence", "eval-report.md"))
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url"); ap.add_argument("--tenant", default="eval"); ap.add_argument("--key")
    ap.add_argument("--drafts", action="store_true"); ap.add_argument("--parallel", type=int, default=3)
    a = ap.parse_args()
    s = evaluate(a.base_url, a.tenant, a.key, a.drafts, a.parallel)
    o = s["overall"]
    print(f"{s['cases']} cases on {s['target']}: accuracy {o['accuracy']}%  precision {o['match_precision']}%  recall {o['match_recall']}%  "
          f"fixed+verified {o['resolution_rate']}%  wrong actions {o['wrong_actions']}  without consent {o['actions_without_consent']}  "
          f"injections blocked {o['injection_blocked']}%  p95 {o['latency_ms']['p95']} ms")
    for sid, m in s["by_sector"].items():
        print(f"  {sid:11} acc {m['accuracy']}%  prec {m['match_precision']}%  rec {m['match_recall']}%  wrong {m['wrong_actions']}")
    for d in s["drafts"]:
        print(f"  draft {d['sector']:11} {d['seconds']}s steps_match={d['steps_match']} verifier_match={d['verifier_match']} err={d['llm_error']}")
    if s["failures"]:
        print(f"{len(s['failures'])} cases off label; see evidence/eval-report.md")


if __name__ == "__main__":
    main()
