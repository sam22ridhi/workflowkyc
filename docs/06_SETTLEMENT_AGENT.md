# The Settlement Agent: post-onboarding monitoring

Audience: judges and engineers. Status: built and tested on a **synthetic ledger**. Nothing here has seen a real acquirer feed.

## 1. Why it exists

Karyakarta stops fraud at the door (KYB), at the shop (Drishti) and at the video call (V-CIP). Money leaves after go-live, so the same merchant twin keeps watching.
The Settlement Agent is not a product of its own: it is the seventh teammate, working on the **existing** Case Detail, Needs Attention queue, Exception Cards and Timeline.
There is no FinOps dashboard, no Operations role and no generic anomaly engine.

The principle is unchanged: **the model reads, code checks, the model explains, a human approves.**

| Part | Does |
|---|---|
| Code (`app/finops/detect.py`) | Detects with two fixed thresholds, reconciles with arithmetic, picks the payments, chooses the recommended action by rule |
| Cognee (the merchant twin) | Supplies what the merchant declared at onboarding (business, turnover, outlet, terminals, verification result); stores the finding back |
| Sarvam | Rewrites the computed brief in plain English; every number in it must appear in the computed facts, or a template replaces it |
| n8n (Sutradhar) | Runs the chain as a workflow with native Cognee nodes |
| A person (KAM) | Decides: resolve or dismiss. The agent never holds or releases money |

## 2. The chain

MONITOR → RECONCILE → INVESTIGATE → CREATE CASE → ESCALATE. Each step is a Timeline event (`Settlement Agent · <STEP>`), so the judge watches it happen live.

1. **MONITOR.** Compare the last 48 hours with the trailing 30-day baseline. Velocity anomaly: window daily volume **> 150%** of baseline. Settlement anomaly: expected vs actual **> 10%** apart.
   Both are strict "greater than". With fewer than 30 days of history the agent says so and makes **no** anomaly claim.
2. **RECONCILE.** Expected (captured − MDR − merchant refunds) vs actual (bank credit). The gap is split into causes that add up: held batches, issuer chargebacks, anything unexplained.
3. **INVESTIGATE.** Pull the merchant's declared profile from the Cognee twin (n8n's native Cognee *recall* node; the backend asks Cognee itself if n8n is down). Attach the specific payments: chargebacks, payments in held batches,
   and payments with two or more of: ticket ≥ 10× the usual, a terminal or city not seen in the baseline, midnight to 6 am, a new payer repeating. Each flagged payment lists its reasons.
4. **CREATE CASE.** The backend opens a real case row `INV-3xxxx` (kind `investigation`, same Cognee dataset as the merchant), with four Exception Cards (velocity, settlement mismatch, new terminal in another city,
   payer concentration and night activity) and a recommended action. A second scan does not open a duplicate.
5. **ESCALATE.** The case is `needs_attention`, route ESCALATE, due in 4 hours: it appears in the existing KAM queue and in Risk Alerts. Its Timeline carries the whole run.

The new-terminal, night, payer and ticket signals are evidence for the investigator. **Only the two thresholds start the agent.**

## 3. Recommended action (by rule, never by the model)

| Situation | Recommendation |
|---|---|
| Velocity anomaly plus a new terminal or city, or concentrated payers | Hold the next settlement and verify the activity (ask for invoices, confirm the terminal with the merchant via Voice Chase) |
| Settlement anomaly only | Reconcile with the bank: ask why the batch is held or short |
| Velocity only | Confirm a genuine sales event with the merchant; no hold |

It is a recommendation. The KAM resolves or dismisses on the investigation case; the server refuses these actions from the agent or from Compliance (HTTP 403).

## 4. The Settlements tab (Case Detail)

Expected settlement, actual settlement, difference (₹ and %), transaction velocity, settlement health; a 32-day volume chart with the baseline; the reconciliation; what changed in the traffic;
the attached payments; and on an investigation, the brief, the recommended steps and what the twin holds. Labelled **Synthetic ledger**. A merchant that is not live yet sees why the tab is empty.

## 5. The demo

Merchant: **Annapurna Sweets & Snacks (KYB-20820)**, a fully activated Stage 10 merchant with about 30 days of normal settlement around ₹40K a day. (A Stage-2 merchant is capped at ₹50k a month, which would contradict a ₹40K/day history.)

1. Open KYB-20820 → **Settlements** tab: healthy.
2. With demo controls on (`CPV_ALLOW_DEMO_REFERENCE=true`): **Inject 48-hour spike (demo)**. This adds about ₹15 lakh in 48 hours from a new terminal in Jaipur, three repeating payers, round amounts at night, a held batch and four chargebacks.
3. **Run settlement check.** In about 15 to 40 seconds the Timeline shows MONITOR, RECONCILE, INVESTIGATE, CREATE CASE, ESCALATE, and a new `INV-` case appears in the KAM queue marked *Settlement investigation*.
4. Open it: exception cards, the twin's declared profile, the attached payments, the recommended action. Resolve or dismiss as the KAM.
5. **Reset** returns to a healthy ledger.

## 6. What was verified, and what was not

Verified live: the whole chain through n8n with the real Cognee recall node and the real Cognee store, Sarvam's brief checked against the numbers, the case in the queue, the full Timeline; 24 backend tests and 12 frontend tests on this feature.

Not verified, and honest limits:
* **The ledger is synthetic.** A real build reads the acquirer's feed; the agent only reads two tables, so only the loader changes.
* **Thresholds are fixed**, not tuned on real merchant behaviour. A festival week will trip the velocity rule; that is why a person decides and the recommendation for velocity-only is "confirm with the merchant".
* **No money movement.** "Hold the settlement" is a recommendation; there is no payout integration.
* **No scheduler.** The check runs when pressed (or when n8n is triggered); a real deployment would run it on a timer.
* Sarvam's brief is optional polish: if it fails or invents a number, a template takes its place and the case is unaffected.
* The merchant twin for the demo merchant holds a synthetic profile.

## 7. Where it lives

`backend/app/finops/` (`ledger.py`, `detect.py`, `service.py`), `backend/app/routes/settlements.py`, `backend/n8n/build_settlement_workflow.py` (workflow *Karyakarta - Settlement agent*, 16 nodes, webhook `karyakarta-settlement-scan`),
`backend/seed/seed_settlements.py` (creates the demo merchant and stores its profile in Cognee), `src/components/kam/SettlementsTab.tsx`, tests `backend/tests/test_settlement_agent.py` and `src/test/settlement.test.tsx`.

Endpoints: `GET /cases/{id}/settlements`, `POST /cases/{id}/settlements/scan`, the n8n steps `…/monitor`, `…/reconcile`, `…/investigate`, `GET /settlements/{id}/memory-summary`, `POST /settlements/{id}/memory/result`,
and the demo controls `…/demo/spike`, `…/demo/reset`. Actions `inv_resolve` and `inv_dismiss` go through `POST /cases/{id}/action` (KAM only).
