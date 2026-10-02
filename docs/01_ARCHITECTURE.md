# Karyakarta: Agentic Architecture

*Team Genesis51 · Paytm Build for India AI Hackathon (Mumbai) · Track 3: Autonomous AI Teammates*

> **The model reads. Code checks. The model explains. A human approves.**
>
> Karyakarta is a team of AI teammates that does the document work of corporate merchant onboarding, so the Key Account
> Manager (KAM) only makes decisions. Every AI step is separated from every decision step by design.

Diagrams are Mermaid: they render on GitHub and in VS Code with a Mermaid preview extension. A rendered version of the
main diagram is also published as the "Karyakarta Architecture" page.

---

## 1. System context

```mermaid
flowchart LR
    M([Merchant signatory])
    K([KAM, maker])
    C([Compliance, checker])

    subgraph KARYA[Karyakarta platform]
        UI[React web app<br/>merchant portal · KAM workspace · compliance view]
        API[FastAPI backend<br/>system of record · rules · audit]
        N8N[n8n<br/>orchestrator]
    end

    subgraph SARVAM[Sarvam]
        DI[Document Intelligence<br/>extract + digitise]
        VA[Samvaad voice agent<br/>Hindi]
    end
    COG[Cognee Cloud<br/>Merchant Digital Twin<br/>knowledge graph]

    subgraph MOCK[Mock today, real tomorrow]
        REG[MCA · GSTN · bank penny-drop]
        TEL[Telephony]
    end

    M -->|uploads documents| UI
    K --> UI
    C --> UI
    UI <-->|REST + live events SSE| API
    API -->|webhook| N8N
    N8N -->|extract, memory, cross-check| API
    API -->|read documents| DI
    N8N -->|native Cognee nodes| COG
    API -->|ask the case| COG
    N8N -.->|place call, later| TEL
    TEL -.-> VA
    VA -.->|call outcome webhook| N8N
    API -->|compare against| REG
    VA -->|speaks to| M
```

Solid lines exist and were exercised. Dotted lines are the seams that need your phone setup (telephony) and a public
address for n8n (call-completed callback).

---

## 2. The agentic architecture: who does what

Five teammates and two human roles. The orchestrator is not an LLM; it is the conductor.

```mermaid
flowchart TB
    subgraph HUMANS[Decision makers: people only]
        KAM([KAM<br/>maker: reviews, approves, forwards])
        CMP([Compliance<br/>checker: four-eyes approval])
    end

    subgraph TEAM[AI teammates: do the work, never decide]
        ORC{{1. Orchestrator<br/>n8n workflows}}
        RD[2. Reader<br/>Sarvam Document Intelligence]
        VR[3. Verifier<br/>10 deterministic rules<br/>no AI pass/fail]
        TW[4. Digital Twin analyst<br/>Cognee knowledge graph]
        VC[5. Voice chaser<br/>Sarvam Samvaad agent, Hindi]
    end

    ORC -->|per document| RD
    RD -->|fields + confidence + page boxes| VR
    ORC -->|summary text| TW
    VR -->|AUTO / ASK / ESCALATE + evidence| KAM
    TW -->|answers with sources| KAM
    KAM -->|click Voice Chase| VC
    VC -->|outcome + transcript| ORC
    VC -.->|asks merchant to fix, never decides| MER([Merchant])
    KAM -->|submit| CMP
    CMP -->|approve / send back| KAM

    classDef human fill:#fff4d6,stroke:#c98a00;
    classDef ai fill:#e6f7fc,stroke:#00BAF2;
    class KAM,CMP,MER human;
    class ORC,RD,VR,TW,VC ai;
```

| # | Teammate | Technology | Autonomy | Hard limit |
|---|---|---|---|---|
| 1 | Orchestrator | n8n (2 workflows, 37 nodes) | Runs the whole pipeline on upload with no human step | Cannot approve; failures never stop a batch |
| 2 | Reader | Sarvam Document Intelligence | Reads every document, locates every value on the page | Reads only; every value carries a confidence and a page box |
| 3 | Verifier | Plain Python rules | Runs 10 cross-document checks and triages the case | Deterministic, repeatable, evidence on every result. **No LLM decides pass or fail** |
| 4 | Digital Twin analyst | Cognee Cloud (graph + its LLM) | Builds the merchant graph, answers questions with sources | Explains and answers; never decides |
| 5 | Voice chaser | Sarvam Samvaad (Hindi, call agent) | Speaks to the merchant about merchant-fixable items | Never discusses items needing KAM judgement; refuses OTPs; promises nothing. Triggered by the KAM today |

**People decide.** `approve`, `submit_to_compliance`, `send_back`, `compliance_approve` are refused by the API with HTTP
403 unless the actor is the right human role, and compliance can act only after the KAM has submitted (stage 5).

---

## 3. Container view (what runs where)

```mermaid
flowchart LR
    subgraph BROWSER[Browser :5173]
        FE[React 18 + Vite + TypeScript<br/>Tailwind · pdf.js evidence viewer<br/>SSE live updates]
    end

    subgraph HOST[Developer machine]
        subgraph BE[FastAPI :8765]
            R1[routes: cases · documents · memory]
            SV[services: extraction · cross_check · crm_form<br/>memory_service · voice_agent · orchestrator]
            DB[(SQLite WAL<br/>6 tables)]
            FS[(storage/ original files)]
            CACHE[(demo_cache/ recorded Sarvam results)]
        end
        subgraph DOCKER[Docker]
            N[n8n 2.41.6 :5678<br/>+ n8n-nodes-cognee 0.7.0]
        end
    end

    SAR[Sarvam cloud]
    COGC[Cognee Cloud]

    FE <-->|HTTP + SSE| R1
    R1 --> SV
    SV --> DB
    SV --> FS
    SV --> CACHE
    SV -->|extract + digitise, rate limited| SAR
    SV -->|ask, circuit breaker| COGC
    R1 -->|webhook| N
    N -->|host.docker.internal:8765| R1
    N -->|native nodes| COGC
```

---

## 4. Sequence: one upload, end to end (measured: about 2 minutes for 8 documents)

```mermaid
sequenceDiagram
    autonumber
    actor M as Merchant
    participant FE as Web app
    participant API as FastAPI
    participant N as n8n
    participant S as Sarvam
    participant CG as Cognee
    actor K as KAM

    M->>FE: drop 8 PDFs (consent given)
    FE->>API: POST /cases/{id}/documents
    API->>API: validate, SHA-256, detect type, store
    API-->>FE: 202 accepted (hashes shown)
    API->>N: webhook {case_id, doc_ids, dataset}
    loop each document
        N->>API: POST /documents/{id}/extract
        API->>S: extract (schema per type) + 9/min limiter
        S-->>API: fields, confidence, page
        API->>API: per-document checks (GSTIN, CIN, IFSC...)
        API-->>N: status
        N->>API: GET memory-summary
        N->>CG: Remember (unique file prefix, background)
        N->>API: report memory result
    end
    API->>S: digitise (layout boxes), background
    N->>CG: Cognify (build the graph, waits)
    N->>API: graph result, then cross-check
    API->>API: 10 rules vs mock registry, triage
    API-->>FE: live events (SSE): route ESCALATE, 4 issues
    K->>FE: opens the case: evidence, CRM form, ask
```

If n8n is unreachable the backend runs the same steps in-process, so an upload never stalls.

---

## 5. Sequence: Voice Chase

```mermaid
sequenceDiagram
    autonumber
    actor K as KAM
    participant FE as Web app
    participant API as FastAPI
    participant N as n8n (voice workflow)
    participant V as Sarvam voice agent
    participant CG as Cognee
    actor M as Merchant

    K->>FE: Voice Chase
    FE->>API: GET /voice-chase/context (preview)
    API-->>FE: opening line, what the agent will ask, what is held back
    K->>FE: Send
    FE->>API: POST /action {voice}
    API->>N: webhook {case_id}
    N->>API: GET /voice-chase/context
    Note over API: only merchant-fixable items.<br/>Escalations are never sent to the agent
    N-->>V: place call (placeholder until telephony is set up)
    V->>M: Hindi call with case variables
    M-->>V: answers
    V-->>N: call completed {outcome, transcript}
    N->>API: record call on the case + timeline
    N->>CG: Remember (call summary, unique prefix)
    N->>CG: Cognify
    K->>FE: Ask this case: what did the merchant say?
```

The placeholder step and the call-completed callback are the only parts waiting on phone setup. Everything after "call
completed" is verified (with rehearsal calls: the live agent talking to a scripted merchant).

---

## 6. Case routing and lifecycle

```mermaid
stateDiagram-v2
    [*] --> Invited: stage 1
    Invited --> DocsUpload: merchant starts KYB
    DocsUpload --> AIVerifying: documents received
    AIVerifying --> KAMReview: 10 checks done, route set

    state KAMReview {
        [*] --> Triage
        Triage --> AUTO: all checks pass
        Triage --> ASK: merchant can fix
        Triage --> ESCALATE: needs human judgement
    }

    KAMReview --> Checker: KAM approves (human)
    Checker --> KAMReview: compliance sends back (human)
    Checker --> SettlementTest: compliance approves (human)
    SettlementTest --> ESign
    ESign --> LiveUnlimited
```

| Route | When | What happens |
|---|---|---|
| **AUTO** | every applicable check passes | KAM approves with one click |
| **ASK** | something the merchant can fix (wrong name on cheque, address drift, missing document) | agent explains in Hindi and asks for the right document |
| **ESCALATE** | any check marked "needs human judgement" (signatory is not a director; a hidden beneficial owner) | KAM decides, with all evidence attached |

Stages 6 to 8 (settlement test, e-agreement, live unlimited) are modelled as lifecycle labels; the integrations behind them
are not built (see section 11).

---

## 7. Data architecture

```mermaid
erDiagram
    CASE ||--o{ DOCUMENT : has
    CASE ||--o{ CHECKRESULT : "latest 10"
    CASE ||--o{ VOICECALL : has
    CASE ||--o{ AUDITEVENT : "append-only"
    CASE ||--o{ CRMOVERRIDE : "KAM edits"
    CASE {
        string id "KYB-20814"
        string slug "cognee dataset suffix"
        string entity_type
        int stage "1 to 8"
        string route "AUTO ASK ESCALATE"
        string graph_status
    }
    DOCUMENT {
        string doc_type "pan gst coi board bank kyc shareholding fssai"
        string sha256
        json fields "value, confidence, page, boxes"
        json checks
        string memory_status
        json memory_data_ids
    }
    CHECKRESULT {
        string check_id
        string status "pass fail warn skip"
        string action "ask or escalate"
        json evidence "doc, field, page, value"
    }
    VOICECALL {
        string outcome
        json transcript
        string memory_status
    }
```

* **SQLite is the system of record** (WAL mode so live streams never block writes). Cognee is only an AI memory over the same
  documents: losing it never loses data or a decision.
* **One Cognee dataset per case** (`case_<slug>`). Per item a unique file prefix (`doc-<id>`, `call-<id>`) because Cognee
  Cloud refuses a re-used file name with different content (HTTP 409).
* **The audit trail is append-only** and is both the timeline the KAM sees and the source of the live event stream.

---

## 8. Trust boundaries and guardrails

```mermaid
flowchart LR
    A[Untrusted input<br/>uploaded PDFs, voice] --> B[AI reads and speaks<br/>Sarvam, Cognee]
    B --> C[Deterministic code<br/>10 rules, role guards]
    C --> D[Human decision<br/>KAM maker, Compliance checker]
    D --> E[(Append-only audit)]
    B -.->|never writes pass/fail| C
```

| Guardrail | Where | Enforced how |
|---|---|---|
| No AI pass/fail | Verifier | Rules are plain Python; Cognee answers questions only |
| Agent cannot approve | `POST /action` | 403 unless actor is the required human role (tested: agent and merchant refused for all four decisions) |
| Four-eyes order | `POST /action` | Compliance actions need stage 5, set only by the KAM's submit |
| Escalations stay with humans | Voice context | Checks marked "escalate" are excluded from the agent's variables |
| Agent safety rules | Voice agent prompt | No OTP/PIN/account numbers on the call, no promises of approval, documents only via the app (verified live) |
| Every value traceable | Extraction | Value, confidence, page and box shown next to the source |
| Honest failure | Everywhere | Errors recorded on the case (extraction error, memory failed, call not placed); nothing is silently faked |

Person-level four-eyes (maker is not the checker) needs real user identities. The prototype has roles, not accounts.

---

## 9. Resilience: what still works when something fails

| Failure | What happens |
|---|---|
| n8n down or workflow unpublished | Backend runs the same pipeline in-process; timeline says so |
| Cognee down / bad key | Extraction, checks, CRM form and UI keep working; documents show "memory failed"; Ask returns a clear 503 unless a saved answer exists. Circuit breaker: 2 failures, 20 s cooldown |
| Sarvam extraction fails | The document is marked error with a readable reason; other documents continue; `DEMO_MODE` serves recorded results |
| Sarvam rate limit (10 submissions/min) | Sliding-window limiter (9/min, 3 in flight) queues the rest |
| Voice call not placed | Timeline records "Voice call not placed" with the prepared items; the KAM's action is still recorded |
| Browser tab open during server reload | Graceful shutdown limited to 2 s so live streams cannot wedge the server |

---

## 10. Deployment topology (prototype)

| Component | Where | Port |
|---|---|---|
| Web app (Vite dev server) | local | 5173 |
| FastAPI backend | local, `run.bat` | 8765 |
| n8n 2.41.6 + `n8n-nodes-cognee` 0.7.0 | Docker, volume `n8n_data` | 5678 |
| Sarvam, Cognee Cloud | SaaS | n/a |

n8n reaches the backend at `host.docker.internal:8765`. Secrets live only in `backend/.env` and in the n8n credential.

---

## 11. Seams: what plugs in next

```mermaid
flowchart LR
    NOW[Built and verified] --> S1[Telephony: replace one n8n node<br/>+ Sarvam call-completed callback]
    NOW --> S2[Real MCA21 / GSTN / bank penny-drop<br/>replaces app/registry/mock_registry.py]
    NOW --> S3[CKYCR lookup: one more check + registry adapter]
    NOW --> S4[Auto-chase on ASK route: n8n branch already marked]
    NOW --> S5[Day-100 monitoring: same merchant graph<br/>+ transaction feed]
    NOW --> S6[Real identities for person-level four-eyes + DPDP consent log]
```

Each seam is a single module or node, not a redesign. Sections 1 and 18 of the technical documentation list what is and is
not built, item by item.
