"""V-CIP preparation. RBI requires an AUTHORISED OFFICIAL to do the video-based customer identification and sign it off.
Karyakarta does not replace that person; it makes their part about 30 seconds:

  1. a Sarvam voice agent runs a short Hindi pre-interview with RANDOMIZED liveness questions (a number to repeat back, today's day, ...);
  2. the officer sees the questions with the expected answers, the transcript, the shop photos and the PAN document side by side, and signs off in one click.

Face matching is NOT automated (no face-recognition model is integrated). The officer compares the faces; the card says so.
"""
import random
import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app import config
from app.db import audit
from app.drishti import service as drishti
from app.models import Case, Document, VcipRecord, utcnow

IST = timezone(timedelta(hours=5, minutes=30))
WEEKDAYS = [("सोमवार", "Monday"), ("मंगलवार", "Tuesday"), ("बुधवार", "Wednesday"), ("गुरुवार", "Thursday"), ("शुक्रवार", "Friday"), ("शनिवार", "Saturday"), ("रविवार", "Sunday")]
MONTHS = [("जनवरी", "January"), ("फ़रवरी", "February"), ("मार्च", "March"), ("अप्रैल", "April"), ("मई", "May"), ("जून", "June"), ("जुलाई", "July"),
          ("अगस्त", "August"), ("सितंबर", "September"), ("अक्टूबर", "October"), ("नवंबर", "November"), ("दिसंबर", "December")]
DIGIT_HI = {"0": "शून्य", "1": "एक", "2": "दो", "3": "तीन", "4": "चार", "5": "पाँच", "6": "छह", "7": "सात", "8": "आठ", "9": "नौ"}


def make_questions(case: Case, dob: str | None, now: datetime | None = None, rng: random.Random | None = None) -> list[dict]:
    """Three questions: always a random number to repeat (cannot be pre-recorded), plus two others picked at random."""
    rng = rng or random.SystemRandom()
    now = (now or datetime.now(IST)).astimezone(IST)
    digits = "".join(rng.choice("123456789") for _ in range(4))
    wd_hi, wd_en = WEEKDAYS[now.weekday()]
    mo_hi, mo_en = MONTHS[now.month - 1]
    pool = [
        {"kind": "weekday", "hi": "आज कौन सा दिन है?", "en": "What day of the week is it today?", "expected": f"{wd_en} ({wd_hi})"},
        {"kind": "month", "hi": "यह कौन सा महीना चल रहा है?", "en": "Which month is it?", "expected": f"{mo_en} ({mo_hi})"},
        {"kind": "legal_name", "hi": "आपकी कंपनी का पूरा नाम क्या है?", "en": "What is the full name of your company?", "expected": case.legal_name},
    ]
    if case.contact_name:
        pool.append({"kind": "own_name", "hi": "कृपया अपना पूरा नाम बताइए।", "en": "Please say your full name.", "expected": case.contact_name})
    if dob:
        pool.append({"kind": "dob", "hi": "अपनी जन्म तिथि बताइए।", "en": "Please say your date of birth.", "expected": dob})
    chosen = rng.sample(pool, 2)
    spoken = " ".join(DIGIT_HI[d] for d in digits)
    first = {"kind": "repeat_number", "hi": f"मैं एक संख्या बोलूँगी: {spoken}। कृपया उसे वैसे ही दोहराइए।",
             "en": f"I will say a number: {' '.join(digits)}. Please repeat it exactly.", "expected": " ".join(digits)}
    qs = [first] + chosen
    rng.shuffle(qs)
    return [{"id": i + 1, **q} for i, q in enumerate(qs)]


def _dob(session: Session, case: Case) -> str | None:
    docs = [d for d in session.exec(select(Document).where(Document.case_id == case.id, Document.doc_type == "director_kyc"))
            if d.fields and (d.fields.get("date_of_birth") or {}).get("value")]
    return sorted(docs, key=lambda d: d.created_at)[-1].fields["date_of_birth"]["value"] if docs else None


def ensure(session: Session, case: Case) -> VcipRecord:
    """The case's V-CIP record (created when the case reaches the V-CIP stage). Idempotent."""
    rec = session.exec(select(VcipRecord).where(VcipRecord.case_id == case.id)).first()
    if rec is None:
        rec = VcipRecord(id=secrets.token_hex(6), case_id=case.id, questions=make_questions(case, _dob(session, case)))
        session.add(rec)
        session.commit()
        session.refresh(rec)
        audit(session, case.id, "agent", "V-CIP prepared",
              "Drishti's verification is done. The voice agent can now run a short Hindi pre-interview, and an authorised official signs off.", "ai")
    return rec


def context(session: Session, case: Case) -> dict:
    """Agent variables + Hindi opening line for the V-CIP pre-interview agent."""
    rec = ensure(session, case)
    qs = rec.questions
    contact = case.contact_name or "Sir/Madam"
    variables = {"case_id": case.id, "merchant_name": case.merchant_name, "contact_name": contact, "question_count": str(len(qs)),
                 **{f"question_{q['id']}_hi": q["hi"] for q in qs}}
    opening = (f"नमस्ते {case.contact_name or 'सर/मैडम'}, मैं पेटीएम से कार्यकर्ता बोल रही हूँ। यह आपके वीडियो केवाईसी से पहले की एक छोटी सी बातचीत है, "
               f"बस {len(qs)} आसान सवाल। क्या अभी हम शुरू कर सकते हैं?")
    return {"case_id": case.id, "should_call": True, "contact_phone": case.contact_phone, "agent_variables": variables,
            "initial_bot_message": opening, "initial_language_name": "Hindi", "held_back_for_kam": [], "kind": "vcip"}


def configured_problem() -> str | None:
    return None if config.SARVAM_VCIP_AGENT_ID else "SARVAM_VCIP_AGENT_ID"


def record_result(session: Session, case: Case, outcome: str, summary: str | None, transcript: list[dict] | None, call_id: str | None) -> dict:
    rec = ensure(session, case)
    rec.outcome, rec.summary, rec.call_id, rec.last_result_at = outcome, summary, call_id, utcnow()
    if transcript:
        rec.transcript = [{"role": str(t.get("role", "?"))[:30], "text": str(t.get("text", ""))[:2000]} for t in transcript][:200]
    spoke = outcome == "reached" and len(rec.transcript or []) >= 2
    if spoke and rec.status == "queued":
        rec.status, rec.interviewed_at = "interviewed", utcnow()
    session.add(rec)
    session.commit()
    title = "V-CIP pre-interview completed" if spoke else "V-CIP pre-interview not completed"
    audit(session, case.id, "agent", title, (summary or "")[:300] or title, "success" if spoke else "warning")
    return {"voice_call_id": None, "case_id": case.id, "outcome": outcome, "title": title, "worth_remembering": False}


def sign_off(session: Session, case: Case, actor: str) -> VcipRecord:
    rec = ensure(session, case)
    had_interview = rec.status == "interviewed"
    rec.status, rec.signed_off_by, rec.signed_off_at = "signed_off", actor, utcnow()
    session.add(rec)
    session.commit()
    audit(session, case.id, actor, "V-CIP signed off",
          "The authorised official signed off after reviewing the pre-interview, the shop photos and the documents."
          if had_interview else "The authorised official signed off WITHOUT a completed Hindi pre-interview on record.", "success" if had_interview else "warning")
    return rec


def view(session: Session, case: Case) -> dict | None:
    rec = session.exec(select(VcipRecord).where(VcipRecord.case_id == case.id)).first()
    if rec is None:
        return None
    pan = [d for d in session.exec(select(Document).where(Document.case_id == case.id, Document.doc_type.in_(["pan", "director_kyc"])))]
    pan_doc = next((d for d in sorted(pan, key=lambda d: d.created_at, reverse=True) if d.doc_type == "pan"), None) or (pan[0] if pan else None)
    cpv = drishti.active_session(session, case.id)
    return {"status": rec.status, "questions": rec.questions, "transcript": rec.transcript or [], "outcome": rec.outcome, "summary": rec.summary,
            "callId": rec.call_id, "interviewedAt": rec.interviewed_at.isoformat() if rec.interviewed_at else None, "signedOffBy": rec.signed_off_by,
            "agentConfigured": configured_problem() is None, "contactPhone": case.contact_phone,
            "referenceDocument": {"docId": pan_doc.id, "filename": pan_doc.filename, "label": pan_doc.doc_type} if pan_doc else None,
            "selfie": bool(cpv and "selfie" in (cpv.captures or {})),
            "shopVerdict": (cpv.result or {}).get("verdict") if cpv else None,
            "faceMatch": {"performed": False, "note": "No face-matching model is integrated. The authorised official compares the live face with the ID photo."}}
