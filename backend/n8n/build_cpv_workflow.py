"""Generates n8n/karyakarta_cpv.n8n.json. Usage: python n8n/build_cpv_workflow.py n8n/karyakarta_cpv.n8n.json

Sutradhar (n8n) runs contact point verification by Drishti.

Flow A, open (POST /webhook/karyakarta-cpv-start {case_id}):
    Compliance approval opens the stage -> create (or fetch) the secure capture link. The link is shown to the merchant in the AI
    Communication Center (no WhatsApp).

Flow B, captured (POST /webhook/karyakarta-cpv-captured {case_id, session_id}):
    The merchant submitted both photos -> Drishti analyses (signboard via Sarvam, distance, capture integrity, screen-replay, MCC)
    -> verified or sent to a person -> the evidence is stored in the case's Cognee dataset (native node, unique file name prefix)
    and the graph is refreshed, so "Ask this case" can answer questions about the shop.
"""
import json
import sys
import uuid

OUT = sys.argv[1]
CRED = {"cogneeApi": {"id": "kkCogneeCloud01", "name": "Cognee Cloud (Karyakarta)"}}


def node(name, type_, version, pos, params, **extra):
    n = {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "karyakarta-cpv/" + name)), "name": name,
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


BO = "={{ $('Settings (open)').first().json.backend_url }}"
CO = "{{ $('Settings (open)').first().json.case_id }}"
BC = "={{ $('Settings (captured)').first().json.backend_url }}"
CC = "{{ $('Settings (captured)').first().json.case_id }}"

nodes = [
    # ------------------------------------------------ Flow A: open verification
    node("Verification opened", "n8n-nodes-base.webhook", 2, [0, 120],
         {"httpMethod": "POST", "path": "karyakarta-cpv-start", "responseMode": "onReceived", "options": {}}, webhookId="karyakarta-cpv-start"),
    setnode("Settings (open)", [220, 120], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.body.case_id }}", "string"),
    ]),
    http("Create secure capture link (Drishti)", [440, 120], "POST", BO + f"/api/cases/{CO}/cpv/link"),
    setnode("Link ready in the AI Communication Center", [660, 120], [
        ("case_id", "={{ $('Settings (open)').first().json.case_id }}", "string"),
        ("status", "={{ $json.data.status }}", "string"),
        ("link", "={{ $json.data.link }}", "string"),
    ]),

    # ------------------------------------------------ Flow B: photos submitted
    node("Photos submitted", "n8n-nodes-base.webhook", 2, [0, 420],
         {"httpMethod": "POST", "path": "karyakarta-cpv-captured", "responseMode": "onReceived", "options": {}}, webhookId="karyakarta-cpv-captured"),
    setnode("Settings (captured)", [220, 420], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.body.case_id }}", "string"),
    ]),
    http("Drishti: analyse the shop", [440, 420], "POST", BC + f"/api/cases/{CC}/cpv/analyse", timeout=240000, onError="continueRegularOutput"),
    if_node("Verified by Drishti?", [660, 420], "={{ $json.data && $json.data.status === 'verified' }}", "boolean", "true"),
    setnode("CPV_VERIFIED: case moves to V-CIP", [900, 340], [
        ("verdict", "CPV_VERIFIED", "string"), ("next", "V-CIP pre-interview and sign-off", "string")]),
    setnode("NEEDS_REVIEW: a person decides", [900, 500], [
        ("verdict", "NEEDS_REVIEW", "string"), ("next", "KAM reviews the evidence: approve or ask for new photos", "string")]),
    http("Get verification memory summary", [1140, 420], "GET", BC + f"/api/cases/{CC}/cpv/memory-summary", onError="continueRegularOutput"),
    # Remember with a unique file name prefix: Cognee Cloud answers 409 when a second upload re-uses a file name with different content.
    node("Cognee: store verification evidence", "n8n-nodes-cognee.cognee", 1, [1380, 420],
         {"resource": "memory", "operation": "remember", "rememberInputType": "text",
          "rememberText": ["={{ $json.data.text }}"], "rememberDatasetName": "={{ $json.data.dataset }}",
          "rememberAdditionalFields": {"fileNamePrefix": "={{ $json.data.file_prefix }}", "runInBackground": True}},
         credentials=CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=3000),
    http("Report evidence stored", [1620, 420], "POST", BC + f"/api/cases/{CC}/cpv/memory/result",
         body="={{ JSON.stringify($json.error ? { status: 'failed', error: String($json.error.message || $json.error).slice(0, 900) } : { status: 'stored' }) }}",
         onError="continueRegularOutput"),
    http("Mark graph building", [1860, 420], "POST", BC + f"/api/cases/{CC}/memory/graph-start", onError="continueRegularOutput"),
    node("Cognee: refresh knowledge graph", "n8n-nodes-cognee.cognee", 1, [2100, 420],
         {"resource": "cognify", "operation": "cognify", "datasets": ["={{ $('Get verification memory summary').first().json.data.dataset }}"],
          "runInBackground": False, "cognifyAdditionalOptions": {}},
         credentials=CRED, onError="continueRegularOutput"),
    http("Report graph result", [2340, 420], "POST", BC + f"/api/cases/{CC}/memory/graph-result",
         body="={{ JSON.stringify(($json.error || JSON.stringify($json).includes('Errored')) ? { status: 'failed', detail: String(($json.error && ($json.error.message || $json.error)) || 'cognify pipeline errored').slice(0, 900) } : { status: 'completed', detail: 'cognify completed' }) }}",
         onError="continueRegularOutput"),
]


def link(*targets):
    return [[{"node": t, "type": "main", "index": 0} for t in group] for group in targets]


connections = {
    "Verification opened": {"main": link(["Settings (open)"])},
    "Settings (open)": {"main": link(["Create secure capture link (Drishti)"])},
    "Create secure capture link (Drishti)": {"main": link(["Link ready in the AI Communication Center"])},
    "Photos submitted": {"main": link(["Settings (captured)"])},
    "Settings (captured)": {"main": link(["Drishti: analyse the shop"])},
    "Drishti: analyse the shop": {"main": link(["Verified by Drishti?"])},
    "Verified by Drishti?": {"main": link(["CPV_VERIFIED: case moves to V-CIP"], ["NEEDS_REVIEW: a person decides"])},
    "CPV_VERIFIED: case moves to V-CIP": {"main": link(["Get verification memory summary"])},
    "NEEDS_REVIEW: a person decides": {"main": link(["Get verification memory summary"])},
    "Get verification memory summary": {"main": link(["Cognee: store verification evidence"])},
    "Cognee: store verification evidence": {"main": link(["Report evidence stored"])},
    "Report evidence stored": {"main": link(["Mark graph building"])},
    "Mark graph building": {"main": link(["Cognee: refresh knowledge graph"])},
    "Cognee: refresh knowledge graph": {"main": link(["Report graph result"])},
}

wf = {"id": "kkCpv00000000001", "name": "Karyakarta - Contact point verification", "nodes": nodes, "connections": connections,
      "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveDataErrorExecution": "all"}, "pinData": {}, "active": False}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2)
print("wrote", OUT, len(nodes), "nodes")
