"""The synthetic settlement ledger of the demo merchant, plus the injectable 48-hour spike.

EVERYTHING HERE IS SYNTHETIC. A real build reads the acquirer's transaction and settlement feed; the agent code (detect.py, service.py)
only reads the LedgerTxn / SettlementBatch tables, so it would not change.

Layout (all in IST calendar days, "today" = the day the ledger was generated):
    days d-32 .. d-3   the 30-day baseline: about Rs 40,000 a day, one outlet in Pune, terminals T-01 / T-02
    days d-2  .. d-1   the 48-hour window the agent evaluates (normal in the healthy ledger; the spike in the injected one)
Settlement money: expected = captured - MDR - merchant refunds. actual = expected, less any held batch, less chargeback debits.
"""
import hashlib
import random
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, delete, select

from app.db import audit
from app.models import Case, LedgerTxn, SettlementBatch, utcnow

IST = timezone(timedelta(hours=5, minutes=30))
MDR_PCT = 0.012                      # merchant discount rate used for the expected net settlement
BASELINE_DAYS = 30
WINDOW_DAYS = 2                      # the "48 hours"
DAILY_TARGET = 40_000

DEMO_CASE_ID = "KYB-20820"
HOME_CITY = "Pune"
HOME_TERMINALS = ("T-01", "T-02")
SPIKE_TERMINAL, SPIKE_CITY = "T-09", "Jaipur"

DEMO_CASE = dict(
    id=DEMO_CASE_ID, slug="annapurna_sweets", merchant_name="Annapurna Sweets & Snacks", legal_name="Annapurna Sweets and Snacks Private Limited",
    entity_type="private_limited", industry="food", mcc="5499", contact_name="Meera Kulkarni", contact_phone=None,
    cin="U15419MH2018PTC310522", pan="AABCA4412H", gstin="27AABCA4412H1Z6",
    registered_address="Shop 7, FC Road, Pune - 411004, Maharashtra",
    stage=10, status="live", account_status="Live · Unlimited", route="AUTO",
    summary="Fully onboarded (synthetic demo merchant). Settlement Agent is monitoring this merchant.", sla=0,
)


def ist_day(dt: datetime) -> date:
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(IST).date()


def today_ist() -> date:
    return ist_day(utcnow())


def _ts(day: date, hour: float) -> datetime:
    base = datetime(day.year, day.month, day.day, tzinfo=IST) + timedelta(hours=hour)
    return base.astimezone(timezone.utc)


def _utr(case_id: str, batch_id: str) -> str:
    return "UTR" + hashlib.sha256(f"{case_id}|{batch_id}".encode()).hexdigest()[:12].upper()


def _normal_day(rng: random.Random, case_id: str, day: date, payers: list[tuple[str, str]]) -> list[LedgerTxn]:
    factor = 1.18 if day.weekday() >= 5 else rng.uniform(0.9, 1.1)
    target = DAILY_TARGET * factor
    out, total = [], 0
    while total < target:
        amount = int(min(max(rng.lognormvariate(5.45, 0.55), 20), 1800))
        hour = rng.choices([9, 11, 13, 16, 18, 20, 21], weights=[1, 2, 4, 2, 4, 5, 2])[0] + rng.random()
        channel, payer = rng.choice(payers)
        out.append(LedgerTxn(case_id=case_id, ts=_ts(day, hour), amount=amount, channel=channel, payer_ref=payer,
                             terminal_id=rng.choices(HOME_TERMINALS, weights=[65, 35])[0], city=HOME_CITY))
        total += amount
    for t in rng.sample(out, max(1, len(out) // 100)):      # about 1% are refunds the merchant initiated (expected deductions)
        out.append(LedgerTxn(case_id=case_id, ts=t.ts + timedelta(hours=1), amount=min(t.amount, 400), status="refund", channel=t.channel,
                             payer_ref=t.payer_ref, terminal_id=t.terminal_id, city=t.city))
    return out


def _spike_txns(rng: random.Random, case_id: str, day: date, share: int) -> list[LedgerTxn]:
    """Large, round, night-time payments from a terminal in another city, from three repeating payers."""
    payers = [("CARD", "CARD ••9031"), ("CARD", "CARD ••5520"), ("UPI", "VPA ••zx90")]
    out = []
    for i in range(share):
        channel, payer = payers[i % 3]
        amount = rng.choice([25_000, 30_000, 40_000, 45_000, 50_000, 60_000, 75_000])
        hour = rng.choice([0.7, 1.2, 2.1, 2.9, 3.4, 4.2, 4.8, 23.4])
        out.append(LedgerTxn(case_id=case_id, ts=_ts(day, hour), amount=amount, channel=channel, payer_ref=payer,
                             terminal_id=SPIKE_TERMINAL, city=SPIKE_CITY))
    return out


def _payers(rng: random.Random) -> list[tuple[str, str]]:
    pool = []
    for _ in range(240):
        kind = rng.choices(["UPI", "CARD", "WALLET"], weights=[72, 22, 6])[0]
        tag = "".join(rng.choices("abcdefghjkmnpqrstuvwxyz23456789", k=4))
        pool.append((kind, f"{'VPA' if kind == 'UPI' else 'CARD' if kind == 'CARD' else 'WALLET'} ••{tag}"))
    return pool


def _books(session: Session, case_id: str, held_payer: str | None = None) -> None:
    """Group each day's payments into settlement batches and compute expected vs actual."""
    txns = list(session.exec(select(LedgerTxn).where(LedgerTxn.case_id == case_id)))
    by_day: dict[date, list[LedgerTxn]] = {}
    for t in txns:
        by_day.setdefault(ist_day(t.ts), []).append(t)
    for day, rows in sorted(by_day.items()):
        ds = day.isoformat()
        batch_a, batch_b = f"B-{day:%Y%m%d}-A", f"B-{day:%Y%m%d}-B"
        held = [t for t in rows if held_payer and t.status == "captured" and t.payer_ref == held_payer and t.terminal_id == SPIKE_TERMINAL]
        for t in rows:
            t.batch_id = batch_b if t in held else batch_a
        for bid, members in ((batch_a, [t for t in rows if t.batch_id == batch_a]), (batch_b, held)):
            if not members:
                continue
            cap = sum(t.amount for t in members if t.status == "captured")
            refunds = sum(t.amount for t in members if t.status == "refund")
            chargebacks = sum(t.amount for t in members if t.status == "chargeback")
            expected = cap - round(cap * MDR_PCT) - refunds
            is_held = bid == batch_b
            session.add(SettlementBatch(id=bid, case_id=case_id, day=ds, status="held" if is_held else "paid", expected=expected,
                                        actual=0 if is_held else expected - chargebacks, utr=None if is_held else _utr(case_id, bid),
                                        hold_reason="Acquirer risk hold: card and UPI payments from a new terminal in another city" if is_held else None))
        for t in rows:
            session.add(t)
    session.commit()


def _wipe(session: Session, case_id: str) -> None:
    session.exec(delete(LedgerTxn).where(LedgerTxn.case_id == case_id))
    session.exec(delete(SettlementBatch).where(SettlementBatch.case_id == case_id))
    session.commit()


def generate(session: Session, case_id: str, spike: bool = False) -> dict:
    """(Re)build the merchant's ledger: 32 normal days, and with spike=True the last 48 hours replaced by the injected spike. Deterministic."""
    _wipe(session, case_id)
    rng = random.Random(f"{case_id}-ledger")
    payers = _payers(rng)
    today = today_ist()
    window = [today - timedelta(days=WINDOW_DAYS - i) for i in range(WINDOW_DAYS)]            # d-2, d-1
    for i in range(BASELINE_DAYS + WINDOW_DAYS, 0, -1):
        day = today - timedelta(days=i)
        for t in _normal_day(rng, case_id, day, payers):
            session.add(t)
        if spike and day in window:
            for t in _spike_txns(random.Random(f"{case_id}-spike-{day}"), case_id, day, 15 if day == window[0] else 13):
                session.add(t)
    session.commit()
    if spike:   # four issuer chargebacks land on the second day
        originals = list(session.exec(select(LedgerTxn).where(LedgerTxn.case_id == case_id, LedgerTxn.terminal_id == SPIKE_TERMINAL,
                                                              LedgerTxn.payer_ref == "CARD ••9031", LedgerTxn.status == "captured").order_by(LedgerTxn.ts)))[:4]
        for o in originals:
            session.add(LedgerTxn(case_id=case_id, ts=_ts(window[1], 15.0), amount=o.amount, status="chargeback", channel="CARD", payer_ref=o.payer_ref,
                                  terminal_id=o.terminal_id, city=o.city, ref_txn_id=o.id))
        session.commit()
    _books(session, case_id, held_payer="CARD ••5520" if spike else None)
    n = len(list(session.exec(select(LedgerTxn.id).where(LedgerTxn.case_id == case_id))))
    return {"case_id": case_id, "spike": spike, "transactions": n}


def ensure_demo_merchant(session: Session) -> bool:
    """Create the synthetic post-onboarding merchant and its healthy 32-day ledger once. Returns True when it created it."""
    if session.get(Case, DEMO_CASE_ID) is not None:
        return False
    from datetime import timedelta as td
    data = dict(DEMO_CASE)
    sla = data.pop("sla")
    session.add(Case(**data, sla_due=utcnow() + td(minutes=sla), operating_address=data["registered_address"], seed_missing=""))
    session.commit()
    audit(session, DEMO_CASE_ID, "merchant", "Application submitted", "Onboarded and activated (synthetic demo merchant; Stage 10, Live Unlimited).", "neutral")
    generate(session, DEMO_CASE_ID, spike=False)
    audit(session, DEMO_CASE_ID, "agent", "Settlement Agent is monitoring",
          "Loaded 32 days of settlement history (synthetic, about ₹40,000 a day). The agent compares every 48 hours with the trailing 30-day baseline.", "ai")
    return True


def profile_text(case: Case) -> str:
    """What the merchant twin (Cognee) holds about this merchant after onboarding: the declared business, the shop and its terminals."""
    return "\n".join([
        f"Merchant profile for {case.legal_name} (trade name {case.merchant_name}, case {case.id}). Fully onboarded; account is Live Unlimited.",
        f"Business: {case.industry} (merchant category code {case.mcc}). Registered and operating address: {case.registered_address}. It runs a single outlet in {HOME_CITY}.",
        f"Declared expected monthly turnover: about 12 lakh rupees (roughly 40,000 rupees a day) with an average ticket of about 260 rupees, mostly UPI and card payments at the counter.",
        f"Payment terminals registered at onboarding: {', '.join(HOME_TERMINALS)}, both at the {HOME_CITY} outlet. No other outlet, branch or online store was declared.",
        "Contact point verification by Drishti: verified (signboard read as the trade name, photographed 4 m from the declared address).",
        f"Identifiers: CIN {case.cin}, PAN {case.pan}, GSTIN {case.gstin}. No adverse registry findings at onboarding.",
        "Onboarding risk route: AUTO (every check passed). This text is a synthetic demo profile.",
    ])
