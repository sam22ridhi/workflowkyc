"""Generates n8n/karyakarta_document_pipeline.n8n.json (n8n 2.x, executionOrder v1). Usage: python n8n/build_workflow.py n8n/karyakarta_document_pipeline.n8n.json"""
import json
import sys
import uuid

OUT = sys.argv[1]
CRED = {"cogneeApi": {"id": "kkCogneeCloud01", "name": "Cognee Cloud (Karyakarta)"}}
B = "={{ $('Settings').first().json.backend_url }}"
DOC = "{{ $('Loop over documents').first().json.doc_id }}"
CASE = "{{ $('Settings').first().json.case_id }}"


def node(name, type_, version, pos, params, **extra):
    n = {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "karyakarta/" + name)), "name": name,
         "type": type_, "typeVersion": version, "position": pos}
    n.update(extra)
    return n


def http(name, pos, method, path, body=None, timeout=60000, **extra):
    p = {"method": method, "url": B.replace(" }}", " }}") + path, "options": {"timeout": timeout}}
    if body is not None:
        p.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, p, **extra)


def setnode(name, pos, fields):
    return node(name, "n8n-nodes-base.set", 3.4, pos, {
        "assignments": {"assignments": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, name + k)), "name": k, "value": v, "type": t}
                                         for k, v, t in fields]}, "options": {}})


nodes = [
    node("Documents uploaded", "n8n-nodes-base.webhook", 2, [0, 300],
         {"httpMethod": "POST", "path": "karyakarta-documents", "responseMode": "onReceived", "options": {}},
         webhookId="karyakarta-documents"),
    setnode("Settings", [220, 300], [
        ("backend_url", "http://host.docker.internal:8765", "string"),
        ("case_id", "={{ $json.body.case_id }}", "string"),
        ("dataset", "={{ $json.body.dataset }}", "string"),
        ("doc_ids", "={{ $json.body.doc_ids }}", "array"),
    ]),
    node("Split out documents", "n8n-nodes-base.splitOut", 1, [440, 300],
         {"fieldToSplitOut": "doc_ids", "options": {"destinationFieldName": "doc_id"}}),
    node("Loop over documents", "n8n-nodes-base.splitInBatches", 3, [660, 300], {"batchSize": 1, "options": {}}),

    # ---- per document
    http("Extract + check (Sarvam via backend)", [900, 460], "POST", f"/api/documents/{DOC}/extract",
         timeout=180000, onError="continueErrorOutput"),
    http("Mark extraction failed", [1140, 640], "POST", f"/api/documents/{DOC}/status",
         body="={{ JSON.stringify({ status: 'error', message: 'n8n: ' + (($json.error && ($json.error.message || $json.error.description)) || 'extraction step failed') }) }}",
         onError="continueRegularOutput"),
    http("Get memory summary", [1140, 400], "GET", f"/api/documents/{DOC}/memory-summary", onError="continueRegularOutput"),
    # Remember (not Add): Cognee Cloud answers 409 to a second upload with the same file name and different content, and the
    # Add operation always names its file "text-1.txt". Remember lets each document get its own file name prefix.
    # Background mode returns in a few seconds; the batch-level cognify below waits until the graph is built.
    node("Cognee: store document", "n8n-nodes-cognee.cognee", 1, [1380, 400],
         {"resource": "memory", "operation": "remember", "rememberInputType": "text",
          "rememberText": ["={{ $json.data.text }}"], "rememberDatasetName": "={{ $json.data.dataset }}",
          "rememberAdditionalFields": {"fileNamePrefix": "={{ $json.data.file_prefix }}", "runInBackground": True}},
         credentials=CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=3000),
    http("Report memory result", [1620, 400], "POST", f"/api/documents/{DOC}/memory/result",
         body="={{ JSON.stringify($json.error ? { status: 'failed', error: String($json.error.message || $json.error).slice(0, 900) } : { status: 'stored', response: $json }) }}",
         onError="continueRegularOutput"),

    # ---- once per batch
    http("Mark graph building", [900, 120], "POST", f"/api/cases/{CASE}/memory/graph-start",
         onError="continueRegularOutput", executeOnce=True),
    node("Cognee: build knowledge graph", "n8n-nodes-cognee.cognee", 1, [1140, 120],
         {"resource": "cognify", "operation": "cognify", "datasets": ["={{ $('Settings').first().json.dataset }}"],
          "runInBackground": False, "cognifyAdditionalOptions": {}},
         credentials=CRED, onError="continueRegularOutput", executeOnce=True),
    http("Report graph result", [1380, 120], "POST", f"/api/cases/{CASE}/memory/graph-result",
         body="={{ JSON.stringify(($json.error || JSON.stringify($json).includes('Errored')) ? { status: 'failed', detail: String(($json.error && ($json.error.message || $json.error)) || 'cognify pipeline errored').slice(0, 900) } : { status: 'completed', detail: 'cognify completed' }) }}",
         onError="continueRegularOutput"),
    http("Cross-check documents", [1620, 120], "POST", f"/api/cases/{CASE}/cross-check", timeout=180000),
    # Side branch (never blocks the cross-check): Remember in background returns no data ids, so list the dataset's items
    # and report {id, name} to the backend; names are "doc-<doc_id>-1", which lets "Ask this case" name its source documents.
    node("Cognee: find case dataset", "n8n-nodes-cognee.cognee", 1, [1620, -120],
         {"resource": "dataset", "operation": "create", "datasetCreateName": "={{ $('Settings').first().json.dataset }}"},
         credentials=CRED, onError="continueRegularOutput", executeOnce=True),
    node("Cognee: list stored items", "n8n-nodes-cognee.cognee", 1, [1860, -120],
         {"resource": "dataset", "operation": "getData", "datasetResourceId": "={{ $json.id }}"},
         credentials=CRED, onError="continueRegularOutput"),
    node("Combine items", "n8n-nodes-base.aggregate", 1, [2100, -120],
         {"aggregate": "aggregateAllItemData", "destinationFieldName": "items", "options": {}}, onError="continueRegularOutput"),
    http("Report stored items", [2340, -120], "POST", f"/api/cases/{CASE}/memory/items",
         body="={{ JSON.stringify({ items: ($json.items || []).map(i => ({ id: i.id, name: i.name })) }) }}",
         onError="continueRegularOutput"),
    node("Issues found?", "n8n-nodes-base.if", 2.2, [1860, 120], {
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                       "conditions": [{"id": "issues-gt-0", "leftValue": "={{ $json.data.issues.length }}", "rightValue": 0,
                                       "operator": {"type": "number", "operation": "gt"}}],
                       "combinator": "and"},
        "options": {}}),
    setnode("Needs attention: voice chase (placeholder)", [2100, 20], [
        ("route", "={{ $json.data.route }}", "string"),
        ("summary", "={{ $json.data.summary }}", "string"),
        ("next_action", "Voice / WhatsApp chase to the merchant goes here (placeholder)", "string"),
    ]),
    setnode("Ready for KAM review", [2100, 220], [
        ("route", "={{ $json.data.route }}", "string"),
        ("summary", "={{ $json.data.summary }}", "string"),
    ]),
]


def link(*targets):
    return [[{"node": t, "type": "main", "index": 0} for t in group] for group in targets]


connections = {
    "Documents uploaded": {"main": link(["Settings"])},
    "Settings": {"main": link(["Split out documents"])},
    "Split out documents": {"main": link(["Loop over documents"])},
    # splitInBatches v3: output 0 = done, output 1 = loop
    "Loop over documents": {"main": link(["Mark graph building"], ["Extract + check (Sarvam via backend)"])},
    "Extract + check (Sarvam via backend)": {"main": link(["Get memory summary"], ["Mark extraction failed"])},
    "Mark extraction failed": {"main": link(["Loop over documents"])},
    "Get memory summary": {"main": link(["Cognee: store document"])},
    "Cognee: store document": {"main": link(["Report memory result"])},
    "Report memory result": {"main": link(["Loop over documents"])},
    "Mark graph building": {"main": link(["Cognee: build knowledge graph"])},
    "Cognee: build knowledge graph": {"main": link(["Report graph result"])},
    "Report graph result": {"main": link(["Cross-check documents", "Cognee: find case dataset"])},
    "Cognee: find case dataset": {"main": link(["Cognee: list stored items"])},
    "Cognee: list stored items": {"main": link(["Combine items"])},
    "Combine items": {"main": link(["Report stored items"])},
    "Cross-check documents": {"main": link(["Issues found?"])},
    "Issues found?": {"main": link(["Needs attention: voice chase (placeholder)"], ["Ready for KAM review"])},
}

wf = {
    "id": "OFViBfvIpWQltfiy",
    "name": "Karyakarta - Document pipeline",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1", "saveManualExecutions": True, "saveDataSuccessExecution": "all",
                 "saveDataErrorExecution": "all"},
    "pinData": {},
    "active": False,
    "meta": {"templateCredsSetupCompleted": True},
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2)
print("wrote", OUT, len(nodes), "nodes")
