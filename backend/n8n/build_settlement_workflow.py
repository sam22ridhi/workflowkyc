"""Generates n8n/karyakarta_settlement.n8n.json. Usage: python n8n/build_settlement_workflow.py n8n/karyakarta_settlement.n8n.json

Sutradhar (n8n) runs the post-onboarding Settlement Agent:
    POST /webhook/karyakarta-settlement-scan {case_id}
    MONITOR      compare the last 48 h with the trailing 30-day baseline (backend: thresholds and arithmetic, no model)
    RECONCILE    expected vs actual settlement, the cause, the specific payments
    INVESTIGATE  recall the merchant's declared profile from the Cognee merchant twin (native Cognee node, memory > recall)
    CREATE CASE  the backend opens the investigation case (Sarvam writes the brief; every number is checked against the ledger)
    ESCALATE     the case lands in the existing KAM Needs Attention queue; every step is a Timeline event
    then the finding is stored back into the merchant twin (native Cognee node, unique file name prefix) and the graph is refreshed.
The agent only recommends: it never holds or releases money.
"""
import json
import sys
import uuid

OUT = sys.argv[1]
CRED = {"cogneeApi": {"id": "kkCogneeCloud01", "name": "Cognee Cloud (Karyakarta)"}}


def node(name, type_, version, pos, params, **extra):
    n = {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "karyakarta-settlement/" + name)), "name": name,
         "type": type_, "typeVersion": version, "position": pos}
    n.update(extra)
    return n


def http(name, pos, method, url, body=None, timeout=30000, **extra):
    p = {"method": method, "url": url, "options": {"timeout": timeout}}
    if body is not None:
        p.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, p, **extra)


def setnode(name, pos, fields):
    return node(name, "n8n-nodes-base.set", 3.4, pos, {
        "assignments": {"assignments": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, name + k)), "name": k, "value": v, "type": t}
                                         for k, v, t in fields]}, "options": {}})


def if_node(name, pos, left, op_type, operation, right=None):
    cond = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, name)), "leftValue": left,
            "operator": {"type": op_type, "operation": operation, **({"singleValue": True} if right is None else {})}}
    if right is not None:
        cond["rightValue"] = right
    return node(name, "n8n-nodes-base.if", 2.2, pos, {
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                       "conditions": [cond], "combinator": "and"}, "options": {}})


MON = "MONITOR: compare with the 30-day baseline"
INV = "INVESTIGATE: open the investigation case"
BS = "={{ $('Settings').first().json.backend_url }}"
CS = "{{ $('Settings').first().json.case_id }}"
INV_ID = "{{ $('" + INV + "').first().json.data.investigation_id }}"
QUESTION = ("What did this merchant declare at onboarding about its business, expected turnover, outlet locations and payment terminals, "
            "and were there any risk notes or verification results?")
# A failed recall must never stop the case: it becomes a labelled gap on the investigation.
CONTEXT_BODY = ("={{ JSON.stringify({ context: (($json.items || []).some(i => i.error)) "
                "? { error: ($json.items.find(i => i.error).error.message || String($json.items.find(i => i.error).error)) } : $json }) }}")

nodes = [
    node("Settlement scan requested", "n8n-nodes-base.webhook", 2, [0, 200],
         {"httpMethod": "POST", "path": "karyakarta-settlement-scan", "responseMode": "onReceived", "options": {}}, webhookId="karyakarta-settlement-scan"),
    setnode("Settings", [220, 200], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.body.case_id }}", "string"),
    ]),
    http(MON, [440, 200], "POST", BS + f"/api/cases/{CS}/settlements/monitor", timeout=60000),
    if_node("Anomaly detected?", [660, 200], "={{ $json.data && $json.data.anomaly === true }}", "boolean", "true"),
    setnode("Healthy, or already under investigation", [900, 360], [
        ("result", "No new case: both thresholds are within limits, or an investigation is already open", "string")]),
    http("RECONCILE: expected vs actual", [900, 100], "POST", BS + f"/api/cases/{CS}/settlements/reconcile", timeout=60000),
    node("Cognee: recall the merchant twin", "n8n-nodes-cognee.cognee", 1, [1140, 100],
         {"resource": "memory", "operation": "recall", "recallQuery": QUESTION,
          "recallDatasets": ["={{ $('" + MON + "').first().json.data.dataset }}"], "recallTopK": 8, "recallSimplify": True},
         credentials=CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=3000),
    node("Combine recall", "n8n-nodes-base.aggregate", 1, [1380, 100],
         {"aggregate": "aggregateAllItemData", "destinationFieldName": "items", "options": {}}, onError="continueRegularOutput"),
    http(INV, [1620, 100], "POST", BS + f"/api/cases/{CS}/settlements/investigate", body=CONTEXT_BODY, timeout=120000),
    if_node("Case created?", [1860, 100], "={{ $json.data && $json.data.created === true }}", "boolean", "true"),
    setnode("No new case", [2100, 240], [("result", "={{ $json.data.reason }}", "string")]),
    http("Get finding memory summary", [2100, 0], "GET", BS + f"/api/settlements/{INV_ID}/memory-summary", onError="continueRegularOutput"),
    # Remember with a unique file name prefix: Cognee Cloud answers 409 when a second upload re-uses a file name with different content.
    node("Cognee: store the finding in the merchant twin", "n8n-nodes-cognee.cognee", 1, [2340, 0],
         {"resource": "memory", "operation": "remember", "rememberInputType": "text",
          "rememberText": ["={{ $json.data.text }}"], "rememberDatasetName": "={{ $json.data.dataset }}",
          "rememberAdditionalFields": {"fileNamePrefix": "={{ $json.data.file_prefix }}", "runInBackground": True}},
         credentials=CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=3000),
    http("Report finding stored", [2580, 0], "POST", BS + f"/api/settlements/{INV_ID}/memory/result",
         body="={{ JSON.stringify($json.error ? { status: 'failed', error: String($json.error.message || $json.error).slice(0, 900) } : { status: 'stored' }) }}",
         onError="continueRegularOutput"),
    node("Cognee: refresh knowledge graph", "n8n-nodes-cognee.cognee", 1, [2820, 0],
         {"resource": "cognify", "operation": "cognify", "datasets": ["={{ $('Get finding memory summary').first().json.data.dataset }}"],
          "runInBackground": True, "cognifyAdditionalOptions": {}},
         credentials=CRED, onError="continueRegularOutput"),
    setnode("Escalated: in the KAM Needs Attention queue", [3060, 0], [
        ("investigation", "={{ $('" + INV + "').first().json.data.investigation_id }}", "string"),
        ("recommended", "={{ $('" + INV + "').first().json.data.recommended.title }}", "string"),
        ("next", "A person (KAM) reviews the evidence and decides. The agent has not moved or held any money.", "string")]),
]


def link(*targets):
    return [[{"node": t, "type": "main", "index": 0} for t in group] for group in targets]


connections = {
    "Settlement scan requested": {"main": link(["Settings"])},
    "Settings": {"main": link([MON])},
    MON: {"main": link(["Anomaly detected?"])},
    "Anomaly detected?": {"main": link(["RECONCILE: expected vs actual"], ["Healthy, or already under investigation"])},
    "RECONCILE: expected vs actual": {"main": link(["Cognee: recall the merchant twin"])},
    "Cognee: recall the merchant twin": {"main": link(["Combine recall"])},
    "Combine recall": {"main": link([INV])},
    INV: {"main": link(["Case created?"])},
    "Case created?": {"main": link(["Get finding memory summary"], ["No new case"])},
    "Get finding memory summary": {"main": link(["Cognee: store the finding in the merchant twin"])},
    "Cognee: store the finding in the merchant twin": {"main": link(["Report finding stored"])},
    "Report finding stored": {"main": link(["Cognee: refresh knowledge graph"])},
    "Cognee: refresh knowledge graph": {"main": link(["Escalated: in the KAM Needs Attention queue"])},
}

wf = {"id": "kkSettle000000001", "name": "Karyakarta - Settlement agent", "nodes": nodes, "connections": connections,
      "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveDataErrorExecution": "all"}, "pinData": {}, "active": False}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2)
print("wrote", OUT, len(nodes), "nodes")
