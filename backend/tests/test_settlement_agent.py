"""Settlement Agent: deterministic detection, reconciliation, the investigation case, role guard, and the Cognee / Sarvam / n8n seams (all faked)."""
import pytest
from sqlmodel import Session, select

from app import config, memory
from app.db import engine
from app.finops import detect, ledger, service
from app.finops.detect import inr
from app.memory.base import AddResult, CognifyResult, MemoryUnavailable, SearchResult
from app.models import AuditEvent, Case, CheckResult, Investigation, LedgerTxn

M = ledger.DEMO_CASE_ID


class FakeStore:
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.added = fail, []

    def add_document(self, dataset, *, file_path, filename, mime, summary_text):
        if self.fail:
            raise MemoryUnavailable("down")
        self.added.append((dataset, filename, summary_text))
        return AddResult("ds", ["d1"])

    def cognify(self, dataset, dataset_id=None, wait=True):
        return CognifyResult("completed", "r", "ok")

    def search(self, dataset, query, search_type="GRAPH_COMPLETION", top_k=15):
        if self.fail:
            raise MemoryUnavailable("down")
        return SearchResult("Single outlet in Pune, terminals T-01 and T-02, about 40,000 rupees a day.", [])

    def health(self):
        return {"available": not self.fail}


@pytest.fixture
def agent(client, monkeypatch):
    """The synthetic merchant with a healthy ledger; Cognee faked, Sarvam off, no n8n; demo controls on."""
    monkeypatch.setattr(config, "CPV_ALLOW_DEMO_REFERENCE", True)
    monkeypatch.setattr(config, "N8N_SETTLEMENT_WEBHOOK_URL", "")
    monkeypatch.setattr(config, "SARVAM_AGENT_API_KEY", "")
    store = FakeStore()
    memory.set_store(store)
    with Session(engine) as s:
        ledger.ensure_demo_merchant(s)
        _clean(s)
        ledger.generate(s, M, spike=False)
    yield {"client": client, "store": store}
    memory.set_store(None)
    with Session(engine) as s:
        _clean(s)


def _clean(s: Session) -> None:
    for e in list(s.exec(select(AuditEvent).where(AuditEvent.case_id == M))):
        if e.action.startswith("Settlement Agent") or e.action.startswith("Demo:") or e.action.startswith("Finding") or e.action.startswith("Settlement check") or "investigation" in e.action.lower():
            s.delete(e)
    s.commit()
    for inv in list(s.exec(select(Investigation))):
        for c in s.exec(select(CheckResult).where(CheckResult.case_id == inv.id)):
            s.delete(c)
        for e in s.exec(select(AuditEvent).where(AuditEvent.case_id == inv.id)):
            s.delete(e)
        s.delete(inv)
        case = s.get(Case, inv.id)
        if case:
            s.delete(case)
    s.commit()


def spike(c):
    assert c.post(f"/api/cases/{M}/settlements/demo/spike").status_code == 200


# ---------------------------------------------------------------- the ledger and the thresholds
def test_healthy_history_is_about_40k_a_day_and_raises_nothing(agent):
    with Session(engine) as s:
        d = detect.evaluate(s, M)
    assert d["eligible"] and d["history_days"] == 30
    assert 36_000 < d["baseline_daily"] < 46_000
    assert d["health"] == "healthy" and not d["velocity_anomaly"] and not d["settlement_anomaly"]
    assert d["expected"] == d["actual"] and d["velocity_pct"] < 130
    assert len(d["series"]) == 32


def test_the_ledger_is_deterministic(agent):
    with Session(engine) as s:
        a = detect.evaluate(s, M)["baseline_daily"]
        ledger.generate(s, M, spike=False)
        assert detect.evaluate(s, M)["baseline_daily"] == a


def test_the_spike_trips_both_thresholds(agent):
    spike(agent["client"])
    with Session(engine) as s:
        d = detect.evaluate(s, M)
    assert d["velocity_anomaly"] and d["velocity_pct"] > 150
    assert d["settlement_anomaly"] and d["difference_pct"] > 10
    assert d["health"] == "critical" and d["anomaly"]
    assert 1_300_000 < d["window_volume"] < 1_800_000                     # about 15 lakh over 48 hours
    assert d["expected"] > d["actual"] > 0


def test_a_merchant_without_30_days_makes_no_claims(agent):
    with Session(engine) as s:
        s.add(Case(id="KYB-NEWBIE", slug="newbie", merchant_name="Newbie", legal_name="Newbie", entity_type="proprietorship", stage=10, status="live"))
        s.commit()
        d = detect.evaluate(s, "KYB-NEWBIE")
        s.delete(s.get(Case, "KYB-NEWBIE"))
        s.commit()
    assert not d["eligible"] and d["health"] == "unknown" and not d["anomaly"] and "30" in d["note"]


def test_thresholds_are_strict_greater_than(agent):
    """Exactly 150% of baseline and exactly 10% apart are NOT anomalies."""
    assert detect.VELOCITY_THRESHOLD == 1.5 and detect.MISMATCH_THRESHOLD == 0.10
    with Session(engine) as s:
        for b in s.exec(select(ledger.SettlementBatch).where(ledger.SettlementBatch.case_id == M)):
            if b.day in detect.windows([])[1]:
                b.actual = b.expected - round(b.expected * 0.09)           # 9% short: below the line
                s.add(b)
        s.commit()
        assert not detect.evaluate(s, M)["settlement_anomaly"]


def test_reconciliation_names_the_cause_and_attaches_the_payments(agent):
    spike(agent["client"])
    with Session(engine) as s:
        det = detect.evaluate(s, M)
        rec = detect.reconcile(s, M, det)
    kinds = {c["kind"]: c for c in rec["causes"]}
    assert "held_batch" in kinds and "chargebacks" in kinds and kinds["chargebacks"]["count"] == 4
    assert abs(sum(c["amount"] for c in rec["causes"]) - rec["difference"]) <= 1          # the causes add up to the gap
    assert rec["new_terminals"] == [ledger.SPIKE_TERMINAL] and rec["new_cities"] == [ledger.SPIKE_CITY]
    assert rec["flagged_total"] >= 20 and rec["flagged"][0]["amount"] >= rec["flagged"][-1]["amount"]
    assert all(f["reasons"] for f in rec["flagged"])
    assert rec["shifts"]["new_terminal_share_pct"] > 80 and rec["shifts"]["night_share_pct"] > 50
    assert any("chargeback" in " ".join(f["reasons"]) for f in rec["flagged"]) and any("held batch" in " ".join(f["reasons"]) for f in rec["flagged"])


def test_recommendation_is_by_rule_and_never_moves_money(agent):
    spike(agent["client"])
    with Session(engine) as s:
        det = detect.evaluate(s, M)
        r = detect.recommend(det, detect.reconcile(s, M, det))
    assert r["severity"] == "high" and "hold" in r["title"].lower() and r["decided_by"].startswith("a person")
    assert any("a person decides" in step for step in r["steps"])


def test_indian_rupee_grouping():
    assert inr(1500000) == "₹15,00,000" and inr(42584) == "₹42,584" and inr(999) == "₹999" and inr(-624780) == "-₹6,24,780"


# ---------------------------------------------------------------- the chain
def test_healthy_merchant_opens_no_case(agent):
    out = service.run_pipeline(M)
    assert out["anomaly"] is False and out["health"] == "healthy"
    with Session(engine) as s:
        assert not list(s.exec(select(Investigation)))
        titles = [e.action for e in s.exec(select(AuditEvent).where(AuditEvent.case_id == M))]
    assert "Settlement Agent · MONITOR" in titles and "Settlement Agent · CREATE CASE" not in titles


def test_anomaly_runs_monitor_reconcile_investigate_create_escalate_in_order(agent):
    spike(agent["client"])
    out = service.run_pipeline(M)
    assert out["anomaly"] and out["created"] and out["investigation_id"] == "INV-30001"
    with Session(engine) as s:
        steps = [e.action.split(" · ")[1] for e in s.exec(select(AuditEvent).where(AuditEvent.case_id == M).order_by(AuditEvent.id)) if e.action.startswith("Settlement Agent · ")]
        assert steps == ["MONITOR", "RECONCILE", "INVESTIGATE", "CREATE CASE", "ESCALATE"]
        inv_case = s.get(Case, "INV-30001")
        assert inv_case.kind == "investigation" and inv_case.parent_case_id == M and inv_case.status == "needs_attention" and inv_case.route == "ESCALATE"
        assert inv_case.slug == s.get(Case, M).slug                                        # same Cognee dataset: the same merchant twin
        checks = {c.check_id: c.status for c in s.exec(select(CheckResult).where(CheckResult.case_id == "INV-30001"))}
        assert checks["velocity"] == "fail" and checks["settlement_mismatch"] == "fail" and checks["new_terminal_location"] == "fail"
        inv = s.get(Investigation, "INV-30001")
        assert inv.reconciliation["flagged_total"] >= 20 and inv.context["source"] == "cognee" and inv.brief_source == "template"
        assert inv.memory_status == "stored"
    with Session(engine) as s:     # the investigation's own Timeline carries the whole run, in order
        child = [e.action.split(" · ")[1] for e in s.exec(select(AuditEvent).where(AuditEvent.case_id == "INV-30001").order_by(AuditEvent.id)) if e.action.startswith("Settlement Agent · ")]
    assert child == ["MONITOR", "RECONCILE", "INVESTIGATE", "CREATE CASE", "ESCALATE"]
    assert any(M and "inv-INV-30001" in a[1] for a in agent["store"].added)                  # the finding went back into the twin


def test_the_case_shows_in_the_existing_needs_attention_queue(agent):
    spike(agent["client"])
    service.run_pipeline(M)
    c = agent["client"]
    rows = {r["id"]: r for r in c.get("/api/cases").json()["data"]["items"]}
    r = rows["INV-30001"]
    assert r["kind"] == "investigation" and r["parentCaseId"] == M and r["route"] == "ESCALATE" and r["isUrgent"] and r["stage"] == "Escalated to KAM"
    detail = c.get("/api/cases/INV-30001").json()["data"]
    assert detail["kind"] == "investigation" and detail["checklist"] == [] and len(detail["findings"]) >= 3
    assert [t["title"] for t in detail["timeline"]].count("Settlement Agent · ESCALATE") == 1
    assert all(i["kind"] != "investigation" or i["stageNumber"] == 10 for i in rows.values())


def test_a_second_scan_does_not_open_a_duplicate(agent):
    spike(agent["client"])
    service.run_pipeline(M)
    again = service.run_pipeline(M)
    assert again["anomaly"] is False and again["already_investigating"] == "INV-30001"
    with Session(engine) as s:
        assert len(list(s.exec(select(Investigation)))) == 1


def test_cognee_down_still_opens_the_case_and_says_so(agent, monkeypatch):
    memory.set_store(FakeStore(fail=True))
    monkeypatch.setattr("app.memory_service.demo_cache.get", lambda *a, **k: None)                 # no saved answer to fall back on
    monkeypatch.setattr("app.memory_service.demo_cache.put", lambda *a, **k: None)
    spike(agent["client"])
    out = service.run_pipeline(M)
    assert out["created"] and out["context_source"] == "unavailable"
    with Session(engine) as s:
        assert s.get(Investigation, "INV-30001").memory_status == "failed"
        tones = {e.action: e.tone for e in s.exec(select(AuditEvent).where(AuditEvent.case_id == M))}
    assert tones["Settlement Agent · INVESTIGATE"] == "warning"


def test_n8n_steps_accept_the_recall_node_output(agent):
    c = agent["client"]
    spike(c)
    assert c.post(f"/api/cases/{M}/settlements/monitor").json()["data"]["anomaly"] is True
    assert c.post(f"/api/cases/{M}/settlements/reconcile").json()["data"]["reconciliation"]["flagged_total"] >= 20
    recall = {"items": [{"json": {"text": "Declared: a single outlet in Pune, terminals T-01 and T-02, about 40,000 rupees a day."}}]}
    out = c.post(f"/api/cases/{M}/settlements/investigate", json={"context": recall}).json()["data"]
    assert out["created"] and out["context_source"] == "cognee"
    with Session(engine) as s:
        assert "single outlet in Pune" in s.get(Investigation, out["investigation_id"]).context["answer"]
    summ = c.get(f"/api/settlements/{out['investigation_id']}/memory-summary").json()["data"]
    assert summ["dataset"] == "case_annapurna_sweets" and summ["file_prefix"] == "inv-INV-30001" and "Recommended action" in summ["text"]
    assert c.post(f"/api/settlements/INV-30001/memory/result", json={"status": "stored"}).json()["data"]["memory_status"] == "stored"


def test_recall_errors_become_a_labelled_gap_not_a_crash(agent):
    assert service.normalise_context({"error": {"message": "timeout"}}, "n8n recall")["source"] == "unavailable"
    assert service.normalise_context([], "n8n recall")["source"] == "empty"


def test_investigate_on_a_healthy_merchant_creates_nothing(agent):
    out = agent["client"].post(f"/api/cases/{M}/settlements/investigate", json={}).json()["data"]
    assert out["created"] is False


# ---------------------------------------------------------------- Sarvam writes, code checks
def test_a_brief_with_an_invented_number_is_replaced_by_the_template(agent, monkeypatch):
    spike(agent["client"])
    monkeypatch.setattr(config, "SARVAM_AGENT_API_KEY", "key")

    class R:
        def __init__(self, text):
            self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]

    texts = iter(["Volume rose 1673% and the gap is ₹6,24,780 but ₹99,99,999 vanished somewhere. " * 2])
    monkeypatch.setattr("app.sarvam.client.client", lambda: type("X", (), {"chat": type("Ch", (), {"completions": staticmethod(lambda **kw: R(next(texts)))})()})())
    with Session(engine) as s:
        m = s.get(Case, M)
        det = detect.evaluate(s, M)
        text, source = service.write_brief(det, detect.reconcile(s, M, det), m, {"source": "cognee", "answer": ""})
    assert source == "template" and "99,99,999" not in text


def test_a_clean_sarvam_brief_is_kept(agent, monkeypatch):
    spike(agent["client"])
    monkeypatch.setattr(config, "SARVAM_AGENT_API_KEY", "key")
    with Session(engine) as s:
        m = s.get(Case, M)
        det = detect.evaluate(s, M)
        good = (f"Volume averaged {inr(det['window_daily'])} a day against {inr(det['baseline_daily'])}. Settlement expected {inr(det['expected'])} but "
                f"{inr(det['actual'])} arrived. This is a recommendation for a person to review, not a finding of fraud.")
        R = lambda text: type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": text})()})()]})()  # noqa: E731
        monkeypatch.setattr("app.sarvam.client.client", lambda: type("X", (), {"chat": type("Ch", (), {"completions": staticmethod(lambda **kw: R("<think>x</think>" + good))})()})())
        text, source = service.write_brief(det, detect.reconcile(s, M, det), m, {"source": "cognee", "answer": ""})
    assert source == "sarvam" and text == good


def test_number_check():
    assert service.numbers_ok("gap ₹6,24,780 or 44.4%", "difference ₹6,24,780 44.4%")
    assert not service.numbers_ok("gap ₹7,00,000", "difference ₹6,24,780")
    assert service.numbers_ok("three payers across 2 days", "")


# ---------------------------------------------------------------- humans decide; roles; demo controls; n8n
def test_only_the_kam_can_resolve_and_only_an_open_investigation(agent):
    c = agent["client"]
    spike(c)
    service.run_pipeline(M)
    assert c.post("/api/cases/INV-30001/action", json={"action": "inv_resolve", "actor": "agent"}).status_code == 403
    assert c.post("/api/cases/INV-30001/action", json={"action": "inv_resolve", "actor": "compliance"}).status_code == 403
    assert c.post(f"/api/cases/{M}/action", json={"action": "inv_resolve", "actor": "kam"}).status_code == 409           # not an investigation
    r = c.post("/api/cases/INV-30001/action", json={"action": "inv_dismiss", "actor": "kam", "note": "tested"})
    assert r.status_code == 200 and r.json()["data"]["stage"] == 10
    with Session(engine) as s:
        assert s.get(Investigation, "INV-30001").status == "dismissed" and s.get(Case, "INV-30001").status == "closed"
    assert c.post("/api/cases/INV-30001/action", json={"action": "inv_resolve", "actor": "kam"}).status_code == 409        # already closed
    kpis = c.get("/api/cases").json()["data"]["kpis"]
    assert kpis["totalOpen"] >= 0


def test_demo_controls_are_off_unless_enabled(agent, monkeypatch):
    monkeypatch.setattr(config, "CPV_ALLOW_DEMO_REFERENCE", False)
    r = agent["client"].post(f"/api/cases/{M}/settlements/demo/spike")
    assert r.status_code == 403 and "disabled" in r.json()["detail"]
    assert agent["client"].get(f"/api/cases/{M}/settlements").json()["data"]["demoControls"] is False


def test_demo_reset_closes_the_investigation_and_heals_the_ledger(agent):
    c = agent["client"]
    spike(c)
    service.run_pipeline(M)
    assert c.post(f"/api/cases/{M}/settlements/demo/reset").status_code == 200
    d = c.get(f"/api/cases/{M}/settlements").json()["data"]
    assert d["detection"]["health"] == "healthy" and d["investigation"] is None


def test_scan_goes_through_n8n_when_configured_and_falls_back_when_it_is_down(agent, monkeypatch):
    import httpx
    c = agent["client"]
    calls = []
    monkeypatch.setattr(config, "N8N_SETTLEMENT_WEBHOOK_URL", "http://n8n.test/webhook/karyakarta-settlement-scan")
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: calls.append((url, json)) or httpx.Response(200, request=httpx.Request("POST", url)))
    assert c.post(f"/api/cases/{M}/settlements/scan").json()["data"]["via"] == "n8n" and calls[0][1] == {"case_id": M}

    def boom(url, json, timeout):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(httpx, "post", boom)
    spike(c)
    assert c.post(f"/api/cases/{M}/settlements/scan").json()["data"]["via"] == "in-process"        # the background task ran before the response returned
    with Session(engine) as s:
        assert s.get(Investigation, "INV-30001") is not None


def test_the_tab_view_for_an_investigation_case_reads_its_merchants_ledger(agent):
    c = agent["client"]
    spike(c)
    service.run_pipeline(M)
    v = c.get("/api/cases/INV-30001/settlements").json()["data"]
    assert v["merchantCaseId"] == M and v["synthetic"] is True and v["investigation"]["id"] == "INV-30001" and v["detection"]["anomaly"]
    assert v["reconciliation"]["flagged"] and v["investigation"]["recommended"]["steps"]
