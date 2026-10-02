"""Generates n8n/karyakarta_voice_chase.n8n.json. Usage: python n8n/build_voice_workflow.py n8n/karyakarta_voice_chase.n8n.json

Flow A, start (POST /webhook/karyakarta-voice-chase {case_id}):
    KAM clicks Voice Chase -> backend -> here: fetch the agent context -> anything to chase? -> place the call -> report.
    The "Place call" node is a PLACEHOLDER until a Sarvam phone number / outbound calling is configured.

Flow B, result (POST /webhook/karyakarta-voice-result {case_id, outcome, summary, transcript, call_id}):
    Sarvam's call-completed callback (or any test payload) -> record the call on the case -> if it was a real call:
    store its summary in the case's Cognee dataset (native Cognee node) -> rebuild the graph -> "Ask this case" can answer
    what the merchant said.
"""
import json
import sys
import uuid

OUT = sys.argv[1]
CRED = {"cogneeApi": {"id": "kkCogneeCloud01", "name": "Cognee Cloud (Karyakarta)"}}


def node(name, type_, version, pos, params, **extra):
    n = {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "karyakarta-voice/" + name)), "name": name,
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


BA = "={{ $('Settings (start)').first().json.backend_url }}"
CA = "{{ $('Settings (start)').first().json.case_id }}"
BB = "={{ $('Settings (result)').first().json.backend_url }}"
CB = "{{ $('Settings (result)').first().json.case_id }}"
CALL_ID = "{{ $('Record call on case').first().json.data.voice_call_id }}"
IN = "$('Call completed').first().json.body"

nodes = [
    # ------------------------------------------------ Flow A: start a chase
    node("Voice chase requested", "n8n-nodes-base.webhook", 2, [0, 200],
         {"httpMethod": "POST", "path": "karyakarta-voice-chase", "responseMode": "onReceived", "options": {}},
         webhookId="karyakarta-voice-chase"),
    setnode("Settings (start)", [220, 200], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.body.case_id }}", "string"),
    ]),
    http("Get agent context", [440, 200], "GET", BA + f"/api/cases/{CA}/voice-chase/context"),
    if_node("Anything to chase?", [660, 200], "={{ $json.data.should_call }}", "boolean", "true"),
    # PLACEHOLDER: replace with the Sarvam outbound-call request once phone calling is configured. It must pass
    # data.agent_variables, data.initial_bot_message and data.contact_phone. The call's outcome then arrives asynchronously
    # at the "Call completed" webhook below, so this node only needs to start the call.
    setnode("Place call (Sarvam phone: set up later)", [900, 120], [
        ("outcome", "not_configured", "string"),
        ("summary", "=Agent context ready ({{ $json.data.agent_variables.issue_count }} item(s): {{ $json.data.agent_variables.documents_needed_en }}). Phone calling is not configured yet.", "string"),
    ]),
    http("Report call not placed", [1140, 120], "POST", BA + f"/api/cases/{CA}/voice-chase/result",
         body="={{ JSON.stringify({ outcome: $json.outcome, summary: $json.summary }) }}"),
    http("Report nothing to chase", [900, 300], "POST", BA + f"/api/cases/{CA}/voice-chase/result",
         body="={{ JSON.stringify({ outcome: 'not_configured', summary: 'No merchant-fixable items on this case, so no call was needed.' }) }}"),

    # ------------------------------------------------ Flow B: a call finished
    node("Call completed", "n8n-nodes-base.webhook", 2, [0, 560],
         {"httpMethod": "POST", "path": "karyakarta-voice-result", "responseMode": "onReceived", "options": {}},
         webhookId="karyakarta-voice-result"),
    setnode("Settings (result)", [220, 560], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.body.case_id }}", "string"),
    ]),
    http("Record call on case", [440, 560], "POST", BB + f"/api/cases/{CB}/voice-chase/result",
         body=f"={{{{ JSON.stringify({{ outcome: {IN}.outcome, summary: {IN}.summary || null, transcript: {IN}.transcript || null, call_id: {IN}.call_id || null }}) }}}}"),
    if_node("Worth remembering?", [660, 560], "={{ $json.data.worth_remembering }}", "boolean", "true"),
    http("Get call memory summary", [900, 480], "GET", BB + f"/api/voice-calls/{CALL_ID}/memory-summary", onError="continueRegularOutput"),
    # Remember with a unique file name prefix: Cognee Cloud answers 409 when a second upload reuses a file name with different
    # content, and the Add operation always names its file "text-1.txt" (so only the first call per case would ever be stored).
    node("Cognee: store call", "n8n-nodes-cognee.cognee", 1, [1140, 480],
         {"resource": "memory", "operation": "remember", "rememberInputType": "text",
          "rememberText": ["={{ $json.data.text }}"], "rememberDatasetName": "={{ $json.data.dataset }}",
          "rememberAdditionalFields": {"fileNamePrefix": "={{ $json.data.file_prefix }}", "runInBackground": True}},
         credentials=CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=3000),
    http("Report call memory result", [1380, 480], "POST", BB + f"/api/voice-calls/{CALL_ID}/memory/result",
         body="={{ JSON.stringify($json.error ? { status: 'failed', error: String($json.error.message || $json.error).slice(0, 900) } : { status: 'stored' }) }}",
         onError="continueRegularOutput"),
    http("Mark graph building", [1620, 480], "POST", BB + f"/api/cases/{CB}/memory/graph-start", onError="continueRegularOutput"),
    node("Cognee: refresh knowledge graph", "n8n-nodes-cognee.cognee", 1, [1860, 480],
         {"resource": "cognify", "operation": "cognify", "datasets": ["={{ $('Get call memory summary').first().json.data.dataset }}"],
          "runInBackground": False, "cognifyAdditionalOptions": {}},
         credentials=CRED, onError="continueRegularOutput"),
    http("Report graph result", [2100, 480], "POST", BB + f"/api/cases/{CB}/memory/graph-result",
         body="={{ JSON.stringify(($json.error || JSON.stringify($json).includes('Errored')) ? { status: 'failed', detail: String(($json.error && ($json.error.message || $json.error)) || 'cognify pipeline errored').slice(0, 900) } : { status: 'completed', detail: 'cognify completed' }) }}",
         onError="continueRegularOutput"),
]


def link(*targets):
    return [[{"node": t, "type": "main", "index": 0} for t in group] for group in targets]


connections = {
    "Voice chase requested": {"main": link(["Settings (start)"])},
    "Settings (start)": {"main": link(["Get agent context"])},
    "Get agent context": {"main": link(["Anything to chase?"])},
    "Anything to chase?": {"main": link(["Place call (Sarvam phone: set up later)"], ["Report nothing to chase"])},
    "Place call (Sarvam phone: set up later)": {"main": link(["Report call not placed"])},
    "Call completed": {"main": link(["Settings (result)"])},
    "Settings (result)": {"main": link(["Record call on case"])},
    "Record call on case": {"main": link(["Worth remembering?"])},
    "Worth remembering?": {"main": link(["Get call memory summary"], [])},
    "Get call memory summary": {"main": link(["Cognee: store call"])},
    "Cognee: store call": {"main": link(["Report call memory result"])},
    "Report call memory result": {"main": link(["Mark graph building"])},
    "Mark graph building": {"main": link(["Cognee: refresh knowledge graph"])},
    "Cognee: refresh knowledge graph": {"main": link(["Report graph result"])},
}

wf = {"id": "kkVoiceChase0001", "name": "Karyakarta - Voice chase", "nodes": nodes, "connections": connections,
      "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveDataErrorExecution": "all"},
      "pinData": {}, "active": False}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2)
print("wrote", OUT, len(nodes), "nodes")
