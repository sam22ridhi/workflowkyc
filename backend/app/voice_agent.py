"""Voice Chase: what the Sarvam Samvaad agent is told about a case, and what comes back from a call.

The agent only raises items the MERCHANT can fix (checks with action='ask' and missing documents). Checks marked
'escalate' (signatory authority, hidden beneficial owners) need a KAM decision and are never discussed on a call.

`context()` returns the agent variables + Hindi opening line. n8n reads it (GET /cases/{id}/voice-chase/context) when it
places a call; `record_result()` stores the outcome n8n reports back (POST /cases/{id}/voice-chase/result).
"""
from sqlmodel import Session, select

from app.db import audit
from app.doctypes import DOC_TYPES, required_for
import uuid

from app.models import Case, CheckResult, Document, VoiceCall, utcnow

KAM_NAME = "Priya"
UPLOAD_PATH = "Paytm for Business app → Account Center → Documents Upload"

# check id -> (English, Hindi, document to send in English, in Hindi)
ASK_PHRASES: dict[str, tuple[str, str, str, str]] = {
    "bank_holder_name": (
        "the account holder name on the cancelled cheque does not match the company's full legal name",
        "कैंसल्ड चेक पर खाताधारक का नाम कंपनी के पूरे कानूनी नाम से मेल नहीं खाता",
        "a cancelled cheque or bank letter showing the full legal name",
        "पूरे कानूनी नाम वाला कैंसल्ड चेक या बैंक का पत्र",
    ),
    "address_consistent": (
        "the address on the GST certificate is different from the address in the application",
        "जीएसटी सर्टिफिकेट का पता आवेदन में दिए गए पते से अलग है",
        "confirmation of the business address, with an address proof or updated GST certificate",
        "व्यवसाय के सही पते की पुष्टि, साथ में पते का प्रमाण या अपडेटेड जीएसटी सर्टिफिकेट",
    ),
    "legal_name_consistent": (
        "the company name is written differently across the documents",
        "दस्तावेज़ों में कंपनी का नाम अलग-अलग लिखा है",
        "documents that show the exact registered company name",
        "कंपनी के सही रजिस्टर्ड नाम वाले दस्तावेज़",
    ),
    "pan_entity_type": (
        "the PAN does not match the company's details",
        "पैन कंपनी के विवरण से मेल नहीं खाता",
        "the company PAN card",
        "कंपनी का पैन कार्ड",
    ),
    "gstin_pan": (
        "the GST number does not match the company PAN",
        "जीएसटी नंबर कंपनी के पैन से मेल नहीं खाता",
        "the correct GST registration certificate",
        "सही जीएसटी रजिस्ट्रेशन सर्टिफिकेट",
    ),
    "cin_match": (
        "the CIN on the incorporation certificate could not be confirmed",
        "इनकॉर्पोरेशन सर्टिफिकेट पर सीआईएन की पुष्टि नहीं हो सकी",
        "a clear copy of the Certificate of Incorporation",
        "इनकॉर्पोरेशन सर्टिफिकेट की साफ़ कॉपी",
    ),
    "licence": (
        "the trade licence is missing, expired or in another name",
        "ट्रेड लाइसेंस नहीं है, समाप्त हो गया है या किसी और के नाम पर है",
        "a valid licence in the company's name",
        "कंपनी के नाम पर वैध लाइसेंस",
    ),
}

DOC_HI = {
    "pan": "कंपनी का पैन कार्ड", "gst": "जीएसटी सर्टिफिकेट", "coi": "इनकॉर्पोरेशन सर्टिफिकेट",
    "board_resolution": "बोर्ड रेज़ोल्यूशन", "bank_cheque": "कैंसल्ड चेक", "director_kyc": "डायरेक्टर का केवाईसी",
    "shareholding": "शेयरहोल्डिंग घोषणा", "fssai": "एफ़एसएसएआई लाइसेंस",
}
SKIP_AS_ITEM = {"required_documents"}     # covered by the missing-document list instead


def _missing_doc_types(session: Session, case: Case) -> list[str]:
    have = {d.doc_type for d in session.exec(select(Document).where(Document.case_id == case.id))}
    seeded = set(filter(None, (case.seed_missing or "").split(","))) if case.seed_missing is not None else None
    out = []
    for t in required_for(case.entity_type, case.industry):
        missing = t not in have and (seeded is None or t in seeded)
        if missing:
            out.append(t)
    return out


def context(session: Session, case: Case) -> dict:
    checks = list(session.exec(select(CheckResult).where(CheckResult.case_id == case.id)))
    asks = [c for c in checks if c.status in {"fail", "warn"} and c.action == "ask" and c.check_id not in SKIP_AS_ITEM]
    held_back = [c.label for c in checks if c.status in {"fail", "warn"} and c.action == "escalate"]
    missing = _missing_doc_types(session, case)

    items_en, items_hi, docs_en, docs_hi = [], [], [], []
    for c in asks:
        en, hi, doc_en, doc_hi = ASK_PHRASES.get(c.check_id, (c.label.lower(), c.label, "a corrected document", "सही दस्तावेज़"))
        items_en.append(en)
        items_hi.append(hi)
        docs_en.append(doc_en)
        docs_hi.append(doc_hi)
    for t in missing:
        items_en.append(f"the {DOC_TYPES[t]} has not been uploaded")
        items_hi.append(f"{DOC_HI.get(t, DOC_TYPES[t])} अपलोड नहीं हुआ है")
        docs_en.append(DOC_TYPES[t])
        docs_hi.append(DOC_HI.get(t, DOC_TYPES[t]))

    contact = case.contact_name or "Sir/Madam"
    contact_hi = case.contact_name or "सर/मैडम"
    numbered = lambda xs: "; ".join(f"{i}. {x}" for i, x in enumerate(xs, 1))
    variables = {
        "case_id": case.id,
        "merchant_name": case.merchant_name,
        "legal_name": case.legal_name,
        "contact_name": contact,
        "kam_name": KAM_NAME,
        "issue_count": str(len(items_en)),
        "issues_en": numbered(items_en) or "none",
        "issues_hi": numbered(items_hi) or "कोई नहीं",
        "documents_needed_en": numbered(docs_en) or "none",
        "documents_needed_hi": numbered(docs_hi) or "कोई नहीं",
        "upload_path": UPLOAD_PATH,
    }
    opening = (f"नमस्ते {contact_hi}, मैं पेटीएम से कार्यकर्ता बोल रही हूँ, {case.merchant_name} के कॉर्पोरेट अकाउंट के "
               f"बारे में। आपके दस्तावेज़ों की जाँच में {len(items_en)} छोटी बातें ठीक करनी हैं। क्या अभी दो मिनट बात हो सकती है?")
    return {
        "case_id": case.id,
        "should_call": bool(items_en),
        "contact_phone": case.contact_phone,
        "agent_variables": variables,
        "initial_bot_message": opening,
        "initial_language_name": "Hindi",
        "held_back_for_kam": held_back,   # never sent to the agent
    }


OUTCOME_TITLES = {
    "reached": ("Voice call: merchant reached", "success"),
    "promised_upload": ("Voice call: merchant will upload", "success"),
    "callback_requested": ("Voice call: callback requested", "warning"),
    "no_answer": ("Voice call: no answer", "warning"),
    "busy": ("Voice call: line busy", "warning"),
    "wrong_number": ("Voice call: wrong number", "warning"),
    "failed": ("Voice call failed", "warning"),
    "not_configured": ("Voice call not placed", "neutral"),
}


def record_result(session: Session, case: Case, outcome: str, summary: str | None, transcript: list[dict] | None,
                  call_id: str | None) -> dict:
    title, tone = OUTCOME_TITLES[outcome]
    transcript = [{"role": str(t.get("role", "?"))[:30], "text": str(t.get("text", ""))[:2000]} for t in (transcript or [])][:200]
    call = VoiceCall(id=uuid.uuid4().hex[:12], case_id=case.id, outcome=outcome, summary=(summary or None) and summary[:2000],
                     transcript=transcript, call_id=call_id, memory_status="n/a" if outcome == "not_configured" else "pending")
    session.add(call)
    session.commit()
    parts = [summary or ""]
    if transcript:
        parts.append("Transcript: " + " | ".join(f"{t['role']}: {t['text']}" for t in transcript))
    if call_id:
        parts.append(f"Call id {call_id}.")
    audit(session, case.id, "agent", title, " ".join(p for p in parts if p).strip()[:2000] or title, tone)
    return {"voice_call_id": call.id, "case_id": case.id, "outcome": outcome, "title": title, "worth_remembering": outcome != "not_configured"}


def memory_summary(session: Session, call: VoiceCall) -> dict:
    """Text n8n's Cognee node stores in the case dataset, so 'Ask this case' can answer what the merchant said."""
    case = session.get(Case, call.case_id)
    lines = [
        f"Voice call record for {case.legal_name} (case {case.id}), {call.created_at:%d %B %Y %H:%M} UTC.",
        f"Contact: {case.contact_name or 'unknown'}. Outcome: {OUTCOME_TITLES[call.outcome][0].removeprefix('Voice call: ')}.",
    ]
    if call.summary:
        lines.append(f"Summary: {call.summary}")
    if call.transcript:
        lines.append("Conversation:")
        lines += [f"- {t['role']}: {t['text']}" for t in call.transcript]
    return {"voice_call_id": call.id, "case_id": case.id, "dataset": f"case_{case.slug}", "file_prefix": f"call-{call.id}",
            "text": "\n".join(lines)}


def record_memory(session: Session, call: VoiceCall, ok: bool, error: str | None) -> dict:
    call.memory_status, call.memory_error = ("stored" if ok else "failed"), (None if ok else (error or "Cognee reported an error")[:400])
    session.add(call)
    session.commit()
    audit(session, call.case_id, "agent", "Voice call stored in Cognee memory" if ok else "Memory unavailable",
          "The call summary can now be searched with Ask this case." if ok else f"{call.memory_error}. The call record itself is unaffected.",
          "ai" if ok else "warning")
    return {"voice_call_id": call.id, "memory_status": call.memory_status}
