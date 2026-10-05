"""The Settlement Agent: MONITOR -> RECONCILE -> INVESTIGATE -> CREATE CASE -> ESCALATE.

The model reads, code checks, the model explains, a human approves:
  * code detects (detect.py: thresholds and arithmetic) and picks the transactions,
  * Cognee (the merchant twin) supplies the merchant's declared context,
  * Sarvam writes the plain-language brief, and every number in it must appear in the computed facts or a template replaces it,
  * the agent only RECOMMENDS. It never holds or releases money; a person (KAM) decides on the investigation case.
Every step is an audit event, so it shows live in the existing Timeline.
"""
import logging
import re
from datetime import timedelta
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app import config
from app.db import audit
from app.finops import detect, ledger
from app.finops.detect import inr
from app.memory import get_store
from app.memory.base import MemoryUnavailable
from app.models import AuditEvent, Case, CheckResult, Investigation, utcnow

log = logging.getLogger("karyakarta.finops")

CONTEXT_QUESTION = ("What did this merchant declare at onboarding about its business, expected turnover, outlet locations and payment terminals, "
                    "and were there any risk notes or verification results?")
SRC = "Settlement ledger (synthetic)"


# ------------------------------------------------------------------ helpers
def merchant_of(session: Session, case: Case) -> Case:
    """An investigation case reads its merchant's ledger; a merchant case is its own."""
    if case.kind == "investigation" and case.parent_case_id:
        return session.get(Case, case.parent_case_id) or case
    return case


def dataset(case: Case) -> str:
    from app import memory_service
    return memory_service.dataset_name(case)


def open_investigation(session: Session, merchant_id: str, window_from: str | None = None) -> Investigation | None:
    q = select(Investigation).where(Investigation.merchant_case_id == merchant_id, Investigation.status == "open")
    if window_from:
        q = q.where(Investigation.window_from == window_from)
    return session.exec(q.order_by(Investigation.created_at.desc())).first()


def emit(session: Session, step: str, detail: str, tone: str, *case_ids: str) -> None:
    for cid in case_ids:
        audit(session, cid, "agent", f"Settlement Agent · {step}", detail, tone)


# ------------------------------------------------------------------ 1. MONITOR
def monitor(session: Session, case: Case) -> dict:
    m = merchant_of(session, case)
    det = detect.evaluate(session, m.id)
    inv = open_investigation(session, m.id, det["window"]["from"]) if det.get("eligible") else None
    base = {"case_id": m.id, "dataset": dataset(m), "detection": det, "anomaly": bool(det.get("anomaly")), "already_investigating": inv.id if inv else None}
    if not det["eligible"]:
        emit(session, "MONITOR", det["note"], "neutral", m.id)
        return base
    window = f"{det['window']['from']} to {det['window']['to']}"
    text = (f"Compared the last 48 hours ({window}) with the trailing {det['baseline_days']}-day baseline. Volume {inr(det['window_daily'])} a day against {inr(det['baseline_daily'])} "
            f"a day ({det['velocity_pct']}% of baseline, threshold {det['thresholds']['velocity_pct']}%). Settlement expected {inr(det['expected'])}, actual {inr(det['actual'])}, "
            f"{det['difference_pct']}% apart (threshold {det['thresholds']['mismatch_pct']}%).")
    if inv:
        emit(session, "MONITOR", text + f" Already under investigation {inv.id}; no duplicate case opened.", "warning", m.id)
        base["anomaly"] = False
    elif det["anomaly"]:
        kinds = " and ".join(k for k, f in (("velocity anomaly", det["velocity_anomaly"]), ("settlement anomaly", det["settlement_anomaly"])) if f)
        emit(session, "MONITOR", text + f" ANOMALY DETECTED: {kinds}.", "warning", m.id)
    else:
        emit(session, "MONITOR", text + " Both within thresholds: healthy.", "success", m.id)
    return base


# ------------------------------------------------------------------ 2. RECONCILE
def do_reconcile(session: Session, case: Case) -> dict:
    m = merchant_of(session, case)
    det = detect.evaluate(session, m.id)
    rec = detect.reconcile(session, m.id, det)
    parts = []
    for c in rec["causes"]:
        if c["kind"] == "held_batch":
            parts.append(f"{inr(c['amount'])} sits in held batch {', '.join(c['batches'])} ({c['txn_count']} payments)")
        elif c["kind"] == "chargebacks":
            parts.append(f"{inr(c['amount'])} was debited as {c['count']} chargebacks")
        elif c["kind"] == "unexplained":
            parts.append(f"{inr(c['amount'])} is unexplained")
    emit(session, "RECONCILE", f"Expected {inr(rec['expected'])}, actual {inr(rec['actual'])}: difference {inr(rec['difference'])} ({rec['difference_pct']}%). "
         + ("; ".join(parts) + ". " if parts else "") + f"{rec['flagged_total']} payments are flagged as the likely cause.", "warning" if rec["difference"] else "ai", m.id)
    return {"case_id": m.id, "detection": det, "reconciliation": rec}


# ------------------------------------------------------------------ 3. context from the merchant twin (Cognee)
def _strings(node, out: list[str]) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in {"id", "dataset_id", "created_at", "updated_at", "score", "dataset_name"}:
                continue
            _strings(v, out)
    elif isinstance(node, list):
        for v in node:
            _strings(v, out)


def normalise_context(raw, via: str) -> dict:
    """Whatever the Cognee recall node (or the backend search) returned -> {source, answer, via}. Never raises."""
    if isinstance(raw, dict) and raw.get("error"):
        return {"source": "unavailable", "answer": "", "via": via, "note": str(raw["error"])[:300]}
    parts: list[str] = []
    _strings(raw, parts)
    seen, uniq = set(), []
    for p in (x.strip() for x in parts):
        if len(p) > 15 and p not in seen:
            seen.add(p)
            uniq.append(p)
    text = " ".join(uniq)[:1500]
    return {"source": "cognee" if text else "empty", "answer": text, "via": via} | ({} if text else {"note": "Cognee returned nothing for this merchant."})


def recall_in_process(case: Case) -> dict:
    """Used when n8n is not running: the same question, asked through the backend's Cognee search."""
    from app import memory_service
    try:
        res = memory_service.ask(case.id, CONTEXT_QUESTION)
        via = "backend search (last saved answer: Cognee was not reachable)" if res.get("from_cache") else "backend search"
        return {"source": "cognee", "answer": str(res.get("answer", ""))[:1500], "via": via}
    except MemoryUnavailable as e:
        return {"source": "unavailable", "answer": "", "via": "backend search", "note": str(e)[:300]}
    except Exception as e:  # noqa: BLE001
        return {"source": "unavailable", "answer": "", "via": "backend search", "note": f"{type(e).__name__}: {e}"[:300]}


# ------------------------------------------------------------------ the brief (Sarvam writes, code checks)
def _facts(det: dict, rec: dict, m: Case) -> dict:
    s = rec["shifts"]
    return {"merchant": m.merchant_name, "baseline_daily": inr(det["baseline_daily"]), "window_daily": inr(det["window_daily"]), "velocity_pct": f"{det['velocity_pct']}%",
            "window_volume": inr(det["window_volume"]), "expected": inr(rec["expected"]), "actual": inr(rec["actual"]), "difference": inr(rec["difference"]),
            "difference_pct": f"{rec['difference_pct']}%", "flagged_count": str(rec["flagged_total"]), "flagged_amount": inr(rec["flagged_amount"]),
            "new_terminals": ", ".join(rec["new_terminals"]) or "none", "new_cities": ", ".join(rec["new_cities"]) or "none",
            "new_terminal_share": f"{s['new_terminal_share_pct']}%", "night_share": f"{s['night_share_pct']}%", "top3_payer_share": f"{s['top3_payer_share_pct']}%",
            "causes": "; ".join(f"{c['kind']} {inr(c['amount'])}" for c in rec["causes"]) or "none"}


def template_brief(det: dict, rec: dict, m: Case, context: dict) -> str:
    f = _facts(det, rec, m)
    decl = " The twin holds the declared profile: a single outlet in %s with terminals T-01 and T-02 and about ₹40,000 a day." % ledger.HOME_CITY if context.get("source") == "cognee" else ""
    return (f"{m.merchant_name}: volume in the last 48 hours averaged {f['window_daily']} a day against a {f['baseline_daily']} baseline ({f['velocity_pct']}). "
            f"Settlement expected {f['expected']} but {f['actual']} arrived, a gap of {f['difference']} ({f['difference_pct']}). "
            f"{f['flagged_count']} payments worth {f['flagged_amount']} are flagged; {f['new_terminal_share']} of volume came from new terminal(s) {f['new_terminals']} "
            f"in {f['new_cities']}, {f['night_share']} was between midnight and 6 am, and the top three payers made up {f['top3_payer_share']}.{decl} "
            "This is a recommendation for review, not a finding of fraud.")


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_ok(text: str, allowed_text: str) -> bool:
    """Every number in the model's brief must appear in the facts it was given (small counts of 10 or less are allowed)."""
    allowed = {n.replace(",", "") for n in _NUM.findall(allowed_text)}
    for n in _NUM.findall(text):
        n = n.replace(",", "").rstrip(".")
        if n in allowed:
            continue
        try:
            if float(n) <= 10:
                continue
        except ValueError:
            pass
        return False
    return True


def write_brief(det: dict, rec: dict, m: Case, context: dict) -> tuple[str, str]:
    """Sarvam explains; the numbers are verified against the computed facts; a template replaces an unverifiable brief."""
    fallback = template_brief(det, rec, m, context)
    if not config.SARVAM_AGENT_API_KEY:
        return fallback, "template"
    facts = _facts(det, rec, m)
    facts_text = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in facts.items())
    ctx = (context.get("answer") or "")[:900]
    prompt = ("Rewrite the analyst brief below in clearer, natural English for a payments risk analyst, at most 110 words, no bullet points. "
              "Keep every figure exactly as written, add no numbers, causes or accusations, and keep the final sentence saying this is a recommendation, not a finding of fraud. "
              "You may use the merchant profile to say what changed against what the merchant declared.\n\n"
              f"BRIEF (computed by code):\n{fallback}\n\nMERCHANT PROFILE FROM THE MERCHANT TWIN (Cognee):\n{ctx or 'not available'}")
    try:
        from app.sarvam.client import client
        r = client().chat.completions(model="sarvam-105b-conversations", temperature=0.2, max_tokens=500,   # the plain model: the reasoning one spends its whole budget thinking
                                      messages=[{"role": "system", "content": "You are a careful risk-operations writer. You never invent facts."},
                                                {"role": "user", "content": prompt}],
                                      request_options={"timeout_in_seconds": 40})
        text = (r.choices[0].message.content or "").strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    except Exception as e:  # noqa: BLE001 - the brief is a nicety; the case and its evidence do not depend on it
        log.warning("Sarvam brief failed (%s: %s); using the template", type(e).__name__, e)
        return fallback, "template"
    if len(text) < 60 or "_" in text or not numbers_ok(text, fallback + " " + facts_text + " " + ctx):
        log.info("Sarvam brief rejected (empty, a field name leaked, or a number not in the facts); using the template. Text was: %s", text[:400])
        return fallback, "template"
    return text, "sarvam"


# ------------------------------------------------------------------ 4-5. INVESTIGATE, CREATE CASE, ESCALATE
def next_investigation_id(session: Session) -> str:
    n = len(list(session.exec(select(Investigation.id))))
    return f"INV-{30001 + n}"


def investigate(session: Session, case: Case, context_raw=None, via: str = "n8n") -> dict:
    m = merchant_of(session, case)
    det = detect.evaluate(session, m.id)
    if not det.get("anomaly"):
        return {"created": False, "reason": "No anomaly in the current window; nothing to investigate."}
    existing = open_investigation(session, m.id, det["window"]["from"])
    if existing:
        return {"created": False, "reason": f"Already under investigation {existing.id}.", "investigation_id": existing.id}
    rec = detect.reconcile(session, m.id, det)
    context = normalise_context(context_raw, via) if context_raw is not None else recall_in_process(m)
    brief, source = write_brief(det, rec, m, context)
    recommended = detect.recommend(det, rec)

    inv_id = next_investigation_id(session)
    inv_ctx_text = ((f"Pulled the merchant's declared profile from the Cognee merchant twin ({context['via']}). " if context["source"] == "cognee"
                     else f"The merchant twin could not be read ({context.get('note', context['source'])}); continuing with the ledger alone. ")
                    + f"Attached {rec['flagged_total']} specific payments ({inr(rec['flagged_amount'])}) as evidence.")
    inv_ctx_tone = "ai" if context["source"] == "cognee" else "warning"
    emit(session, "INVESTIGATE", inv_ctx_text, inv_ctx_tone, m.id)

    inv_case = Case(id=inv_id, slug=m.slug, kind="investigation", parent_case_id=m.id, merchant_name=m.merchant_name, legal_name=m.legal_name, entity_type=m.entity_type,
                    industry=m.industry, cin=m.cin, pan=m.pan, gstin=m.gstin, registered_address=m.registered_address, operating_address=m.operating_address,
                    mcc=m.mcc, contact_name=m.contact_name, contact_phone=m.contact_phone, stage=10, account_status=m.account_status, status="needs_attention",
                    route="ESCALATE", summary=brief, seed_missing="", graph_status=m.graph_status, sla_due=utcnow() + timedelta(hours=4))
    session.add(inv_case)
    session.add(Investigation(id=inv_id, merchant_case_id=m.id, window_from=det["window"]["from"], window_to=det["window"]["to"], detection=det, reconciliation=rec,
                              context=context, brief=brief, brief_source=source, recommended=recommended))
    s = rec["shifts"]
    ev = lambda field, value: [{"doc_id": None, "doc_type": None, "field": field, "page": None, "value": value, "source": SRC}]  # noqa: E731
    checks = [
        ("velocity", "Transaction velocity", "fail" if det["velocity_anomaly"] else "pass",
         f"The last 48 hours averaged {inr(det['window_daily'])} a day, {det['velocity_pct']}% of the {inr(det['baseline_daily'])} baseline (threshold {det['thresholds']['velocity_pct']}%).",
         ev("Daily volume", f"{inr(det['window_daily'])} vs {inr(det['baseline_daily'])}")),
        ("settlement_mismatch", "Settlement mismatch", "fail" if det["settlement_anomaly"] else "pass",
         f"Expected {inr(rec['expected'])}, actual {inr(rec['actual'])}: {inr(rec['difference'])} ({rec['difference_pct']}%) apart (threshold {det['thresholds']['mismatch_pct']}%). "
         + "; ".join(f"{inr(c['amount'])} {c['kind'].replace('_', ' ')}" for c in rec["causes"]) + ".",
         ev("Expected vs actual", f"{inr(rec['expected'])} vs {inr(rec['actual'])}")),
        ("new_terminal_location", "New terminal in another city", "fail" if (s["new_terminal_share_pct"] >= 30 or s["new_city_share_pct"] >= 30) else "pass",
         f"{s['new_terminal_share_pct']}% of window volume came from terminal(s) {', '.join(rec['new_terminals']) or 'none new'} in {', '.join(rec['new_cities']) or 'no new city'}; "
         f"the merchant declared one outlet in {ledger.HOME_CITY}.", ev("Terminal / city", f"{', '.join(rec['new_terminals'])} / {', '.join(rec['new_cities'])}")),
        ("payer_concentration", "Payer concentration and night activity", "fail" if (s["top3_payer_share_pct"] >= 50 or s["night_share_pct"] >= 40) else "pass",
         f"Three payers made {s['top3_payer_share_pct']}% of window volume; {s['night_share_pct']}% was between midnight and 6 am; {s['big_ticket_share_pct']}% came from tickets "
         f"far above the usual {inr(s['usual_ticket'])}.", ev("Top 3 payers", f"{s['top3_payer_share_pct']}% of volume")),
    ]
    for cid, label, status, detail, evidence in checks:
        session.add(CheckResult(case_id=inv_id, check_id=cid, label=label, status=status, detail=detail, action="escalate" if status == "fail" else None, evidence=evidence))
    session.commit()

    _copy_run_events(session, m.id, inv_id, inv_ctx_text, inv_ctx_tone)
    emit(session, "CREATE CASE", f"Opened investigation {inv_id} from the merchant's case {m.id}. Recommended action: {recommended['title']}. {brief_source_note(source)}", "ai", m.id, inv_id)
    emit(session, "ESCALATE", f"Placed {inv_id} in the KAM Needs Attention queue (route ESCALATE, due in 4 hours). The agent has not moved or held any money; a person decides.", "warning", m.id, inv_id)
    return {"created": True, "investigation_id": inv_id, "brief": brief, "brief_source": source, "recommended": recommended, "flagged": rec["flagged_total"], "context_source": context["source"]}


def _copy_run_events(session: Session, merchant_id: str, inv_id: str, investigate_text: str, investigate_tone: str) -> None:
    """The investigation's Timeline shows the whole run: the MONITOR and RECONCILE events of this run are copied over (same time), then INVESTIGATE."""
    for step in ("MONITOR", "RECONCILE"):
        ev = session.exec(select(AuditEvent).where(AuditEvent.case_id == merchant_id, AuditEvent.action == f"Settlement Agent · {step}").order_by(AuditEvent.id.desc())).first()
        if ev is not None:
            session.add(AuditEvent(case_id=inv_id, ts=ev.ts, actor=ev.actor, action=ev.action, detail=ev.detail, tone=ev.tone))
    session.commit()
    emit(session, "INVESTIGATE", investigate_text, investigate_tone, inv_id)


def brief_source_note(source: str) -> str:
    return "Brief written by Sarvam, numbers verified against the ledger." if source == "sarvam" else "Brief generated from the computed facts (template)."


# ------------------------------------------------------------------ memory: the finding goes back into the merchant twin
def memory_summary(session: Session, inv_id: str) -> dict:
    inv = session.get(Investigation, inv_id)
    case = session.get(Case, inv.merchant_case_id)
    rec, det = inv.reconciliation, inv.detection
    top = "\n".join(f"- {f['ref']} {f['ts']} {inr(f['amount'])} {f['status']} via {f['terminal']} {f['city']} from {f['payer']}: {'; '.join(f['reasons'])}" for f in rec["flagged"][:6])
    text = (f"Settlement investigation {inv.id} for {case.legal_name} (case {case.id}), opened {inv.created_at:%d %b %Y} for the window {inv.window_from} to {inv.window_to}. "
            f"Volume was {det['velocity_pct']}% of the 30-day baseline and settlement differed by {det['difference_pct']}% ({inr(det['difference'])}). {inv.brief} "
            f"Recommended action: {inv.recommended['title']}. Status: {inv.status}.\nKey payments:\n{top}")
    return {"investigation_id": inv.id, "case_id": case.id, "dataset": dataset(case), "file_prefix": f"inv-{inv.id}", "text": text, "ready": True}


def record_memory_result(session: Session, inv_id: str, ok: bool, error: str | None) -> dict:
    inv = session.get(Investigation, inv_id)
    inv.memory_status = "stored" if ok else "failed"
    session.add(inv)
    session.commit()
    if ok:
        audit(session, inv.merchant_case_id, "agent", "Finding stored in the merchant twin", f"Investigation {inv.id} was added to the merchant's Cognee dataset, so \"Ask this case\" can answer about it.", "ai")
    else:
        audit(session, inv.merchant_case_id, "agent", "Finding not stored in memory", f"{(error or 'Cognee unavailable')[:200]}. The investigation itself is unaffected.", "warning")
    return {"investigation_id": inv.id, "memory_status": inv.memory_status}


def store_in_process(session: Session, inv_id: str) -> None:
    """Fallback when n8n is not running: add the finding to Cognee through the backend's store."""
    summ = memory_summary(session, inv_id)
    path = Path(config.STORAGE_DIR) / summ["case_id"] / "settlements"
    path.mkdir(parents=True, exist_ok=True)
    f = path / f"{summ['file_prefix']}.txt"
    f.write_text(summ["text"], encoding="utf-8")
    try:
        store = get_store()
        store.add_document(summ["dataset"], file_path=str(f), filename=f.name, mime="text/plain", summary_text=summ["text"])
        store.cognify(summ["dataset"], wait=False)
        record_memory_result(session, inv_id, True, None)
    except Exception as e:  # noqa: BLE001
        record_memory_result(session, inv_id, False, str(e))


# ------------------------------------------------------------------ the whole chain, in-process (n8n runs the same steps as a workflow)
def run_pipeline(case_id: str) -> dict:
    from app.db import engine
    with Session(engine) as s:
        case = s.get(Case, case_id)
        m = merchant_of(s, case)
        mon = monitor(s, m)
        if not mon["anomaly"]:
            return {"anomaly": False, "already_investigating": mon["already_investigating"], "health": mon["detection"].get("health")}
        do_reconcile(s, m)
        out = investigate(s, m, None, "backend search")
        if out.get("created"):
            store_in_process(s, out["investigation_id"])
        return {"anomaly": True, **out}


def trigger(m_case_id: str) -> str:
    """Hand the scan to n8n (Sutradhar) when configured; returns 'n8n' or 'in-process'."""
    url = config.N8N_SETTLEMENT_WEBHOOK_URL
    if url:
        try:
            httpx.post(url, json={"case_id": m_case_id}, timeout=5).raise_for_status()
            return "n8n"
        except httpx.HTTPError as e:
            log.warning("n8n settlement webhook failed (%s)%s", e, "; running in-process" if config.N8N_FALLBACK_INPROCESS else "")
            if not config.N8N_FALLBACK_INPROCESS:
                raise
    return "in-process"


# ------------------------------------------------------------------ human decisions on the investigation case
def close(session: Session, case: Case, action: str, actor: str, note: str | None) -> None:
    inv = session.get(Investigation, case.id)
    if inv is None:
        return
    inv.status, inv.closed_by = ("resolved" if action == "inv_resolve" else "dismissed"), actor
    case.status = "closed"
    session.add(inv)
    session.add(case)
    session.commit()
    verb = "resolved" if action == "inv_resolve" else "dismissed as a false positive"
    audit(session, inv.merchant_case_id, "kam", f"Investigation {inv.id} {verb}", note or "Closed by the KAM.", "success" if action == "inv_resolve" else "neutral")


# ------------------------------------------------------------------ the Settlements tab
def view(session: Session, case: Case) -> dict:
    m = merchant_of(session, case)
    det = detect.evaluate(session, m.id)
    inv = None
    if case.kind == "investigation":
        inv = session.get(Investigation, case.id)
    if inv is None:
        inv = open_investigation(session, m.id)
    rec = inv.reconciliation if inv else (detect.reconcile(session, m.id, det) if det.get("anomaly") else None)
    return {"merchantCaseId": m.id, "merchantName": m.merchant_name, "synthetic": True, "detection": det, "reconciliation": rec,
            "investigation": ({"id": inv.id, "status": inv.status, "brief": inv.brief, "briefSource": inv.brief_source, "recommended": inv.recommended, "context": inv.context,
                               "memoryStatus": inv.memory_status, "createdAt": inv.created_at.isoformat()} if inv else None),
            "demoControls": config.CPV_ALLOW_DEMO_REFERENCE, "monitored": m.kind == "merchant" and m.stage >= 10}
