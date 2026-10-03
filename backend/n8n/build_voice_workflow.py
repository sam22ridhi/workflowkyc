"""Generates n8n/karyakarta_voice_chase.n8n.json. Usage: python n8n/build_voice_workflow.py n8n/karyakarta_voice_chase.n8n.json

Flow A, start (POST /webhook/karyakarta-voice-chase {case_id, to_number}):
    KAM clicks Send Voice Chase -> backend validates the number -> here: get the agent context -> place the call
    (backend -> Sarvam Instant Outbound, from the connected Twilio number) -> wait and poll until the call ends ->
    record the outcome and transcript.

Flow B, result (POST /webhook/karyakarta-voice-result {case_id, outcome, summary, transcript, call_id}):
    An already-finished call (rehearsals, or Sarvam's call-completed callback once n8n is publicly reachable).

Both flows end in the same steps: record the call on the case, and if it was a real call store it in the case's Cognee
dataset (native Cognee node) and refresh the graph, so "Ask this case" can answer what the merchant said.
"""
import json
import sys
import uuid

OUT = sys.argv[1]
CRED = {"cogneeApi": {"id": "kkCogneeCloud01", "name": "Cognee Cloud (Karyakarta)"}}
POLL_SECONDS = 15
MAX_POLLS = 60            # 15 minutes


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
PLACED = "$('Place call (Sarvam)').first().json.data"

nodes = [
    # ------------------------------------------------ Flow A: place the call and follow it
    node("Voice chase requested", "n8n-nodes-base.webhook", 2, [0, 200],
         {"httpMethod": "POST", "path": "karyakarta-voice-chase", "responseMode": "onReceived", "options": {}},
         webhookId="karyakarta-voice-chase"),
    setnode("Settings (start)", [220, 200], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.body.case_id }}", "string"),
        ("to_number", "={{ $json.body.to_number }}", "string"),
    ]),
    http("Get agent context", [440, 200], "GET", BA + f"/api/cases/{CA}/voice-chase/context"),
    if_node("Anything to chase?", [660, 200], "={{ $json.data.should_call }}", "boolean", "true"),
    http("Place call (Sarvam)", [900, 120], "POST", BA + f"/api/cases/{CA}/voice-chase/call", timeout=45000,
         body="={{ JSON.stringify({ to_number: $('Settings (start)').first().json.to_number }) }}", onError="continueRegularOutput"),
    if_node("Call placed?", [1120, 120], "={{ $json.ok === true }}", "boolean", "true"),
    setnode("Call not placed", [1340, 260], [
        ("case_id", "={{ $('Settings (start)').first().json.case_id }}", "string"),
        ("outcome", "not_configured", "string"),
        ("summary", "={{ ($json.error && typeof $json.error === 'string') ? $json.error : 'The call could not be placed.' }}", "string"),
        ("transcript", "={{ [] }}", "array"),
        ("call_id", "", "string"),
    ]),
    node("Wait before checking", "n8n-nodes-base.wait", 1.1, [1340, 40],
         {"resume": "timeInterval", "amount": POLL_SECONDS, "unit": "seconds"}, webhookId=str(uuid.uuid5(uuid.NAMESPACE_URL, "karyakarta-voice/wait"))),
    http("Check call", [1560, 40], "GET", BA + f"/api/cases/{CA}/voice-chase/attempts/{{{{ {PLACED}.attempt_id }}}}", onError="continueRegularOutput"),
    if_node("Call finished or timed out?", [1780, 40],
            f"={{{{ ($json.data && $json.data.state === 'done') || $runIndex >= {MAX_POLLS - 1} }}}}", "boolean", "true"),
    setnode("Result from call", [2000, 40], [
        ("case_id", "={{ $('Settings (start)').first().json.case_id }}", "string"),
        ("outcome", "={{ ($json.data && $json.data.state === 'done') ? $json.data.outcome : 'failed' }}", "string"),
        ("summary", "={{ ($json.data && $json.data.state === 'done') ? $json.data.summary : 'No result arrived from Sarvam within 15 minutes. Check the attempt in the Sarvam console.' }}", "string"),
        ("transcript", "={{ ($json.data && $json.data.transcript) ? $json.data.transcript : [] }}", "array"),
        ("call_id", "={{ ($json.data && $json.data.call_id) ? $json.data.call_id : " + PLACED + ".attempt_id }}", "string"),
    ]),
    http("Report nothing to chase", [900, 320], "POST", BA + f"/api/cases/{CA}/voice-chase/result",
         body="={{ JSON.stringify({ outcome: 'not_configured', summary: 'No merchant-fixable items on this case, so no call was needed.' }) }}"),

    # ------------------------------------------------ Flow B: an already finished call
    node("Call completed", "n8n-nodes-base.webhook", 2, [0, 560],
         {"httpMethod": "POST", "path": "karyakarta-voice-result", "responseMode": "onReceived", "options": {}},
         webhookId="karyakarta-voice-result"),
    setnode("Result from webhook", [2000, 560], [
        ("case_id", "={{ $json.body.case_id }}", "string"),
        ("outcome", "={{ $json.body.outcome }}", "string"),
        ("summary", "={{ $json.body.summary || '' }}", "string"),
        ("transcript", "={{ $json.body.transcript || [] }}", "array"),
        ("call_id", "={{ $json.body.call_id || '' }}", "string"),
    ]),

    # ------------------------------------------------ shared: record, remember
    setnode("Settings (result)", [2220, 300], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.case_id }}", "string"),
        ("outcome", "={{ $json.outcome }}", "string"),
        ("summary", "={{ $json.summary }}", "string"),
        ("transcript", "={{ $json.transcript }}", "array"),
        ("call_id", "={{ $json.call_id }}", "string"),
    ]),
    http("Record call on case", [2440, 300], "POST", BB + f"/api/cases/{CB}/voice-chase/result",
         body="={{ (() => { const r = $('Settings (result)').first().json; return JSON.stringify({ outcome: r.outcome, summary: r.summary || null, transcript: (r.transcript && r.transcript.length) ? r.transcript : null, call_id: r.call_id || null }); })() }}"),
    if_node("Worth remembering?", [2660, 300], "={{ $json.data.worth_remembering }}", "boolean", "true"),
    http("Get call memory summary", [2900, 220], "GET", BB + f"/api/voice-calls/{CALL_ID}/memory-summary", onError="continueRegularOutput"),
    # Remember with a unique file name prefix: Cognee Cloud answers 409 when a second upload re-uses a file name with different
    # content, and the Add operation always names its file "text-1.txt".
    node("Cognee: store call", "n8n-nodes-cognee.cognee", 1, [3140, 220],
         {"resource": "memory", "operation": "remember", "rememberInputType": "text",
          "rememberText": ["={{ $json.data.text }}"], "rememberDatasetName": "={{ $json.data.dataset }}",
          "rememberAdditionalFields": {"fileNamePrefix": "={{ $json.data.file_prefix }}", "runInBackground": True}},
         credentials=CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=3000),
    http("Report call memory result", [3380, 220], "POST", BB + f"/api/voice-calls/{CALL_ID}/memory/result",
         body="={{ JSON.stringify($json.error ? { status: 'failed', error: String($json.error.message || $json.error).slice(0, 900) } : { status: 'stored' }) }}",
         onError="continueRegularOutput"),
    http("Mark graph building", [3620, 220], "POST", BB + f"/api/cases/{CB}/memory/graph-start", onError="continueRegularOutput"),
    node("Cognee: refresh knowledge graph", "n8n-nodes-cognee.cognee", 1, [3860, 220],
         {"resource": "cognify", "operation": "cognify", "datasets": ["={{ $('Get call memory summary').first().json.data.dataset }}"],
          "runInBackground": False, "cognifyAdditionalOptions": {}},
         credentials=CRED, onError="continueRegularOutput"),
    http("Report graph result", [4100, 220], "POST", BB + f"/api/cases/{CB}/memory/graph-result",
         body="={{ JSON.stringify(($json.error || JSON.stringify($json).includes('Errored')) ? { status: 'failed', detail: String(($json.error && ($json.error.message || $json.error)) || 'cognify pipeline errored').slice(0, 900) } : { status: 'completed', detail: 'cognify completed' }) }}",
         onError="continueRegularOutput"),
]


def link(*targets):
    return [[{"node": t, "type": "main", "index": 0} for t in group] for group in targets]


connections = {
    "Voice chase requested": {"main": link(["Settings (start)"])},
    "Settings (start)": {"main": link(["Get agent context"])},
    "Get agent context": {"main": link(["Anything to chase?"])},
    "Anything to chase?": {"main": link(["Place call (Sarvam)"], ["Report nothing to chase"])},
    "Place call (Sarvam)": {"main": link(["Call placed?"])},
    "Call placed?": {"main": link(["Wait before checking"], ["Call not placed"])},
    "Wait before checking": {"main": link(["Check call"])},
    "Check call": {"main": link(["Call finished or timed out?"])},
    "Call finished or timed out?": {"main": link(["Result from call"], ["Wait before checking"])},     # not finished: wait and poll again
    "Result from call": {"main": link(["Settings (result)"])},
    "Call not placed": {"main": link(["Settings (result)"])},
    "Call completed": {"main": link(["Result from webhook"])},
    "Result from webhook": {"main": link(["Settings (result)"])},
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
