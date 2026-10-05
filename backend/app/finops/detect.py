"""Deterministic detection and reconciliation. No model decides anything here: thresholds and arithmetic only.

    velocity anomaly    average daily volume of the last 48 h is more than 150% of the trailing 30-day baseline
    settlement anomaly  expected vs actual settlement for the 48 h differs by more than 10%

The "signals" (new terminal, new city, payer concentration, night share, big tickets) are evidence for the investigator. They never trigger the agent.
"""
from collections import Counter
from datetime import timedelta

from sqlmodel import Session, select

from app.finops.ledger import BASELINE_DAYS, HOME_CITY, IST, WINDOW_DAYS, ist_day, today_ist
from app.models import LedgerTxn, SettlementBatch

VELOCITY_THRESHOLD = 1.5             # > 150% of baseline volume
MISMATCH_THRESHOLD = 0.10            # > 10% expected vs actual
BIG_TICKET_MULTIPLE = 10             # a payment 10x the usual average is flagged
BIG_TICKET_FLOOR = 10_000
NIGHT_HOURS = range(0, 6)
MAX_FLAGGED = 25


def inr(n: float) -> str:
    """Indian digit grouping: 1,500,000 -> ₹15,00,000."""
    n = int(round(n))
    sign, s = ("-" if n < 0 else ""), str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"{sign}₹{s}"


def _load(session: Session, case_id: str):
    txns = list(session.exec(select(LedgerTxn).where(LedgerTxn.case_id == case_id).order_by(LedgerTxn.ts)))
    batches = list(session.exec(select(SettlementBatch).where(SettlementBatch.case_id == case_id).order_by(SettlementBatch.day)))
    return txns, batches


def windows(txns: list[LedgerTxn]):
    """(baseline days, window days) as ISO strings. The window is the last two full IST days before today."""
    today = today_ist()
    win = [(today - timedelta(days=WINDOW_DAYS - i)).isoformat() for i in range(WINDOW_DAYS)]
    start = today - timedelta(days=WINDOW_DAYS + BASELINE_DAYS)
    base = [(start + timedelta(days=i)).isoformat() for i in range(BASELINE_DAYS)]
    return base, win


def evaluate(session: Session, case_id: str) -> dict:
    txns, batches = _load(session, case_id)
    base_days, win_days = windows(txns)
    vol: dict[str, int] = {}
    for t in txns:
        if t.status == "captured":
            d = ist_day(t.ts).isoformat()
            vol[d] = vol.get(d, 0) + t.amount
    history_days = sum(1 for d in base_days if vol.get(d))
    out = {"eligible": history_days >= BASELINE_DAYS, "history_days": history_days, "baseline_days": BASELINE_DAYS,
           "window": {"from": win_days[0], "to": win_days[-1]}, "thresholds": {"velocity_pct": int(VELOCITY_THRESHOLD * 100), "mismatch_pct": int(MISMATCH_THRESHOLD * 100)}}
    series = []
    by_batch_day: dict[str, list[SettlementBatch]] = {}
    for b in batches:
        by_batch_day.setdefault(b.day, []).append(b)
    for d in base_days + win_days:
        bs = by_batch_day.get(d, [])
        series.append({"day": d, "volume": vol.get(d, 0), "expected": sum(b.expected for b in bs), "actual": sum(b.actual for b in bs), "window": d in win_days})
    out["series"] = series
    if not out["eligible"]:
        return {**out, "health": "unknown", "velocity_anomaly": False, "settlement_anomaly": False, "anomaly": False,
                "note": f"Only {history_days} days of history: the agent needs {BASELINE_DAYS} to set a baseline, so it makes no anomaly claims yet."}

    baseline_daily = sum(vol.get(d, 0) for d in base_days) / BASELINE_DAYS
    window_volume = sum(vol.get(d, 0) for d in win_days)
    window_daily = window_volume / len(win_days)
    ratio = window_daily / baseline_daily if baseline_daily else 0.0
    expected = sum(b.expected for d in win_days for b in by_batch_day.get(d, []))
    actual = sum(b.actual for d in win_days for b in by_batch_day.get(d, []))
    diff = expected - actual
    diff_pct = (abs(diff) / expected) if expected else 0.0
    n_win = sum(1 for t in txns if t.status == "captured" and ist_day(t.ts).isoformat() in win_days)
    n_base = sum(1 for t in txns if t.status == "captured" and ist_day(t.ts).isoformat() in base_days)
    velocity_anomaly = ratio > VELOCITY_THRESHOLD
    settlement_anomaly = diff_pct > MISMATCH_THRESHOLD
    health = "critical" if (velocity_anomaly and settlement_anomaly) else "watch" if (velocity_anomaly or settlement_anomaly) else "healthy"
    return {**out, "baseline_daily": round(baseline_daily), "window_volume": window_volume, "window_daily": round(window_daily),
            "velocity_ratio": round(ratio, 2), "velocity_pct": round(ratio * 100),
            "txns_per_day_baseline": round(n_base / BASELINE_DAYS, 1), "txns_per_day_window": round(n_win / len(win_days), 1),
            "expected": expected, "actual": actual, "difference": diff, "difference_pct": round(diff_pct * 100, 1),
            "velocity_anomaly": velocity_anomaly, "settlement_anomaly": settlement_anomaly, "anomaly": velocity_anomaly or settlement_anomaly, "health": health}


def reconcile(session: Session, case_id: str, detection: dict | None = None) -> dict:
    """Explain the expected-vs-actual gap with the specific payments and batches behind it, and what changed about the traffic."""
    det = detection or evaluate(session, case_id)
    txns, batches = _load(session, case_id)
    base_days, win_days = windows(txns)
    in_base = [t for t in txns if ist_day(t.ts).isoformat() in base_days and t.status == "captured"]
    in_win = [t for t in txns if ist_day(t.ts).isoformat() in win_days]
    cap_win = [t for t in in_win if t.status == "captured"]
    base_terminals = {t.terminal_id for t in in_base}
    base_cities = {t.city for t in in_base}
    base_payers = {t.payer_ref for t in in_base}
    avg_ticket = (sum(t.amount for t in in_base) / len(in_base)) if in_base else 0
    big = max(BIG_TICKET_FLOOR, BIG_TICKET_MULTIPLE * avg_ticket)

    held = {b.id: b for b in batches if b.status == "held" and b.day in win_days}
    payer_counts = Counter(t.payer_ref for t in cap_win)
    repeaters = {p for p, c in payer_counts.items() if c >= 3 and p not in base_payers}

    flagged = []
    for t in in_win:
        why = []
        if t.status == "chargeback":
            why.append("chargeback debited by the issuer, not in the expected settlement")
        if t.batch_id in held:
            why.append(f"in held batch {t.batch_id}")
        if t.status == "captured":
            if t.amount >= big:
                why.append(f"ticket {inr(t.amount)} is {t.amount / avg_ticket:.0f}x the usual average {inr(avg_ticket)}" if avg_ticket else f"ticket {inr(t.amount)}")
            if t.terminal_id not in base_terminals:
                why.append(f"terminal {t.terminal_id} was not seen in the 30-day baseline")
            if t.city not in base_cities:
                why.append(f"city {t.city} is not where the merchant operates ({HOME_CITY})")
            if t.ts.astimezone(IST).hour in NIGHT_HOURS:
                why.append("taken between midnight and 6 am")
            if t.payer_ref in repeaters:
                why.append(f"payer {t.payer_ref} paid {payer_counts[t.payer_ref]} times and is new")
        if len(why) >= 2 or t.status == "chargeback" or t.batch_id in held:
            flagged.append({"id": t.id, "ref": f"TXN-{t.id}", "ts": t.ts.astimezone(IST).strftime("%d %b %H:%M"), "amount": t.amount, "status": t.status,
                            "channel": t.channel, "terminal": t.terminal_id, "city": t.city, "payer": t.payer_ref, "batch": t.batch_id, "reasons": why})
    flagged.sort(key=lambda f: -f["amount"])
    total_flagged = len(flagged)

    window_batches = [b for b in batches if b.day in win_days]
    days = [{"day": d, "expected": sum(b.expected for b in window_batches if b.day == d), "actual": sum(b.actual for b in window_batches if b.day == d)} for d in win_days]
    for d in days:
        d["difference"] = d["expected"] - d["actual"]
    held_amount = sum(b.expected for b in held.values())
    cb = [t for t in in_win if t.status == "chargeback"]
    cb_amount = sum(t.amount for t in cb)
    explained = held_amount + cb_amount
    causes = []
    if held:
        causes.append({"kind": "held_batch", "amount": held_amount, "batches": sorted(held), "reason": next(iter(held.values())).hold_reason,
                       "txn_count": sum(1 for t in in_win if t.batch_id in held)})
    if cb:
        causes.append({"kind": "chargebacks", "amount": cb_amount, "count": len(cb)})
    unexplained = det.get("difference", 0) - explained
    if abs(unexplained) > 0:
        causes.append({"kind": "unexplained", "amount": unexplained})

    def share(pred) -> float:
        total = sum(t.amount for t in cap_win)
        return round(100 * sum(t.amount for t in cap_win if pred(t)) / total, 1) if total else 0.0

    top3 = sum(c for _, c in Counter({p: sum(t.amount for t in cap_win if t.payer_ref == p) for p in payer_counts}).most_common(3))
    total_win = sum(t.amount for t in cap_win)
    shifts = {"new_terminal_share_pct": share(lambda t: t.terminal_id not in base_terminals), "new_city_share_pct": share(lambda t: t.city not in base_cities),
              "night_share_pct": share(lambda t: t.ts.astimezone(IST).hour in NIGHT_HOURS),
              "top3_payer_share_pct": round(100 * top3 / total_win, 1) if total_win else 0.0,
              "big_ticket_share_pct": share(lambda t: t.amount >= big), "usual_ticket": round(avg_ticket)}
    return {"window": det["window"], "expected": det.get("expected", 0), "actual": det.get("actual", 0), "difference": det.get("difference", 0),
            "difference_pct": det.get("difference_pct", 0.0), "days": days, "causes": causes, "shifts": shifts,
            "flagged": flagged[:MAX_FLAGGED], "flagged_total": total_flagged,
            "flagged_amount": sum(f["amount"] for f in flagged if f["status"] == "captured"),
            "new_terminals": sorted({t.terminal_id for t in cap_win} - base_terminals), "new_cities": sorted({t.city for t in cap_win} - base_cities)}


def recommend(det: dict, rec: dict) -> dict:
    """The recommended action, by rules. It is only ever a recommendation: a person decides, and the agent never moves money."""
    s = rec["shifts"]
    traffic = s["new_terminal_share_pct"] >= 30 or s["new_city_share_pct"] >= 30
    concentrated = s["top3_payer_share_pct"] >= 50
    steps = []
    if det.get("velocity_anomaly") and (traffic or concentrated):
        title = "Hold the next settlement and verify the activity"
        steps += ["Place the next settlement batch on hold pending review (a person decides; the agent has not moved any money).",
                  "Ask the merchant for invoices or contracts for the largest flagged payments and for the top repeating payers.",
                  "Confirm with the merchant whether terminal %s in %s is theirs (Voice Chase can call them)." % (", ".join(rec["new_terminals"]) or "unknown", ", ".join(rec["new_cities"]) or "another city")]
        severity = "high"
    elif det.get("settlement_anomaly"):
        title = "Reconcile the settlement with the bank"
        steps += ["Ask the acquirer why batch(es) %s are held or short and request release or a written reason." % (", ".join(next((c["batches"] for c in rec["causes"] if c["kind"] == "held_batch"), [])) or "in the window"),
                  "Tell the merchant the expected release date."]
        severity = "medium"
    else:
        title = "Confirm the sales event with the merchant"
        steps += ["Call the merchant to confirm a genuine sales event (festival, bulk order). No hold is recommended."]
        severity = "low"
    if any(c["kind"] == "chargebacks" for c in rec["causes"]):
        steps.append("Review the chargebacks with the acquirer: they are debited from settlement and often signal card testing.")
    steps.append("Close the investigation as resolved or dismiss it as a false positive, with a note.")
    return {"title": title, "severity": severity, "steps": steps, "decided_by": "a person (KAM)"}
