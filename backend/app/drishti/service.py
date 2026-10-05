"""Drishti: sessions, capture rules, analysis and the verdict.

A session is a one-time capture link. The merchant's phone posts two photos (storefront with signboard, billing counter or QR stand) with GPS,
bearing and a timestamp. Drishti then runs five checks:

  HARD (a pass on all four earns the autonomous CPV_VERIFIED)
    capture_integrity   both photos present and sized, camera-stream capture without a camera EXIF block, fresh clock, accurate GPS,
                        both photos taken at the same place
    signboard_name      Sarvam reads the exterior photo; the trade name from the GST certificate must be on the sign
    proximity           the photo's GPS is within CPV_RADIUS_M (Haversine) of the declared address
    screen_replay       frequency-spectrum heuristic for a photo of a screen (assistive; calibrated on synthetic images)
  SOFT
    mcc_inventory       words read on the counter photo fit the declared merchant category code (assistive)

Drishti never fails a shop on its own: anything short of a clean pass is NEEDS_REVIEW and a person decides.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import Session, select

from app import config
from app.db import audit, engine
from app.drishti import geo, vision
from app.models import STAGE_CPV, STAGE_VCIP, Case, CpvSession, Document, utcnow
from app.sarvam import client as sarvam
from app.sarvam.normalise import digitise_text

REQUIRED = ("exterior", "counter")
OPTIONAL = ("selfie",)
KINDS = REQUIRED + OPTIONAL
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_SIDE = 480
MAX_UPLOADS = 12
SAME_PLACE_M = 75.0
VERDICT_VERIFIED, VERDICT_REVIEW = "CPV_VERIFIED", "NEEDS_REVIEW"


class CpvError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- sessions
def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def active_session(session: Session, case_id: str) -> CpvSession | None:
    rows = list(session.exec(select(CpvSession).where(CpvSession.case_id == case_id, CpvSession.status != "superseded").order_by(CpvSession.created_at.desc())))
    return rows[0] if rows else None


def new_session(session: Session, case: Case, supersede: bool = True) -> CpvSession:
    if supersede:
        for old in session.exec(select(CpvSession).where(CpvSession.case_id == case.id, CpvSession.status.in_(["waiting", "captured", "needs_review"]))):
            old.status, old.updated_at = "superseded", utcnow()
            session.add(old)
    s = CpvSession(id=secrets.token_hex(6), case_id=case.id, token=secrets.token_urlsafe(24),
                   expires_at=utcnow() + timedelta(hours=config.CPV_LINK_HOURS))
    session.add(s)
    session.commit()
    session.refresh(s)
    audit(session, case.id, "agent", "Shop verification link ready",
          f"Drishti created a secure camera-only link for the merchant. It expires in {config.CPV_LINK_HOURS:g} hours.", "ai")
    return s


def ensure_session(session: Session, case: Case) -> CpvSession:
    """The case's current usable session (creating one when there is none or the link has expired)."""
    s = active_session(session, case.id)
    if s is None or (s.status == "waiting" and _aware(s.expires_at) < datetime.now(timezone.utc)):
        s = new_session(session, case)
    return s


def link_for(s: CpvSession) -> str:
    return f"{config.PUBLIC_APP_URL}/cpv/{s.token}"


def by_token(session: Session, token: str) -> CpvSession:
    s = session.exec(select(CpvSession).where(CpvSession.token == token)).first()
    if s is None:
        raise CpvError("This verification link is not valid.", 404)
    if s.status == "superseded":
        raise CpvError("This link has been replaced by a newer one. Please use the latest link.", 410)
    if _aware(s.expires_at) < datetime.now(timezone.utc) and s.status in {"waiting", "captured"}:
        raise CpvError("This verification link has expired. Ask your account manager for a new one.", 410)
    return s


# ---------------------------------------------------------------- capture
def _client_time(raw) -> datetime:
    """Accepts epoch milliseconds, epoch seconds or an ISO string."""
    try:
        v = float(raw)
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError as e:
            raise CpvError("The capture has no valid timestamp.") from e


def store_capture(session: Session, s: CpvSession, case: Case, kind: str, image: bytes, *, lat, lon, accuracy_m, heading, client_ts, source: str) -> dict:
    if kind not in KINDS:
        raise CpvError(f"Unknown photo type '{kind}'.")
    if s.status not in {"waiting", "captured"}:
        raise CpvError("This verification is already being reviewed, so no more photos can be added.", 409)
    if s.uploads >= MAX_UPLOADS:
        raise CpvError("Too many attempts on this link. Ask your account manager for a new one.", 429)
    if source == "demo_upload" and not config.CPV_ALLOW_DEMO_REFERENCE:
        raise CpvError("Uploading a photo is disabled. Take the photo with the camera.", 403)
    if not image or len(image) > MAX_IMAGE_BYTES:
        raise CpvError("The photo is empty or larger than 8 MB.")
    if image[:3] != b"\xff\xd8\xff":
        raise CpvError("Only a JPEG photo taken with the camera is accepted.")
    try:
        width, height = vision.image_size(image)
    except Exception as e:  # noqa: BLE001
        raise CpvError("The photo could not be read.") from e
    if min(width, height) < MIN_SIDE:
        raise CpvError(f"The photo is too small ({width}x{height}). Hold the phone steady and capture again.")
    try:
        lat, lon = float(lat), float(lon)
        accuracy = float(accuracy_m)
    except (TypeError, ValueError) as e:
        raise CpvError("Location is required. Allow location access and capture again.") from e
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        raise CpvError("The location in the photo is not valid.")
    when = _client_time(client_ts)
    skew = abs((datetime.now(timezone.utc) - when).total_seconds())
    if skew > config.CPV_MAX_CLOCK_SKEW_S:
        raise CpvError("The photo's time does not match the current time. Capture the photo again now.")
    try:
        hd = float(heading) if heading not in (None, "", "null") else None
    except (TypeError, ValueError):
        hd = None

    folder = Path(config.STORAGE_DIR) / case.id / "cpv"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{s.id}_{kind}.jpg"
    path.write_bytes(image)
    meta = {"path": str(path), "sha256": hashlib.sha256(image).hexdigest(), "lat": lat, "lon": lon, "accuracy_m": round(accuracy, 1), "heading": hd,
            "client_ts": when.isoformat(), "server_ts": utcnow().isoformat(), "skew_s": round(skew, 1), "source": source,
            "width": width, "height": height, "bytes": len(image), "exif": vision.exif_info(image)}
    s.captures = {**(s.captures or {}), kind: meta}
    s.uploads += 1
    s.updated_at = utcnow()
    session.add(s)
    session.commit()
    audit(session, case.id, "merchant", f"Shop photo captured: {kind}", f"{width}x{height}, GPS accuracy {accuracy:.0f} m"
          + (f", bearing {hd:.0f} degrees" if hd is not None else "") + ".", "neutral")
    return meta


def submit(session: Session, s: CpvSession, case: Case) -> None:
    missing = [k for k in REQUIRED if k not in (s.captures or {})]
    if missing:
        raise CpvError("Both photos are needed: " + " and ".join(missing) + ".")
    s.status, s.updated_at = "captured", utcnow()
    session.add(s)
    session.commit()
    audit(session, case.id, "merchant", "Shop photos submitted", "Both photos were sent to Drishti for verification.", "ai")


# ---------------------------------------------------------------- reading the photos
def _ocr(path: str, sha: str) -> str:
    from app.extraction import _call                              # cached Sarvam call (DEMO_MODE and outage fallback)
    out = _call("digitise", sha, lambda: sarvam.digitise(path), lambda msg: None)
    return digitise_text(out["raw"])


def _has_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text or "")


def _latin(text: str) -> str:
    """Devanagari -> Latin with Sarvam transliteration ('शर्मा फूडस' -> 'Sharma Foods'). Empty when there is nothing to convert or the call fails."""
    if not _has_devanagari(text):
        return ""
    try:
        lines = [ln for ln in text.splitlines() if _has_devanagari(ln)][:8]
        joined = "\n".join(lines)[:900]
        out = sarvam.client().text.transliterate(input=joined, source_language_code="hi-IN", target_language_code="en-IN")
        return (out.transliterated_text or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _trade_name(session: Session, case: Case) -> tuple[str, str]:
    docs = [d for d in session.exec(select(Document).where(Document.case_id == case.id, Document.doc_type == "gst")) if d.fields and (d.fields.get("trade_name") or {}).get("value")]
    if docs:
        return sorted(docs, key=lambda d: d.created_at)[-1].fields["trade_name"]["value"], "GST certificate"
    return case.merchant_name, "merchant application"


def _check(id_: str, label: str, status: str, detail: str, **extra) -> dict:
    return {"id": id_, "label": label, "status": status, "detail": detail, **extra}


# ---------------------------------------------------------------- the analysis
def analyse(session_id: str) -> dict:
    """Run all checks, store the result, and (only on a clean pass) advance the case. Never raises on bad evidence."""
    with Session(engine) as db:
        s = db.get(CpvSession, session_id)
        if s is None:
            raise CpvError("Verification session not found.", 404)
        case = db.get(Case, s.case_id)
        if s.status == "analysing":
            return s.result
        missing = [k for k in REQUIRED if k not in (s.captures or {})]
        if missing:
            raise CpvError("Both photos are needed before Drishti can analyse: " + " and ".join(missing) + ".")
        s.status, s.updated_at = "analysing", utcnow()
        db.add(s)
        db.commit()
        audit(db, case.id, "agent", "Drishti is verifying the shop", "Reading the signboard, measuring the distance and checking the photos.", "ai")

        ext, cnt = s.captures["exterior"], s.captures["counter"]
        checks: list[dict] = []

        # 1 capture integrity ---------------------------------------------------------------
        problems = []
        demo_uploads = [k for k in REQUIRED if s.captures[k].get("source") == "demo_upload"]
        for kind in REQUIRED:
            c = s.captures[kind]
            if kind in demo_uploads:
                if c.get("accuracy_m", 9999) > config.CPV_MAX_ACCURACY_M:
                    problems.append(f"the {kind} photo's GPS accuracy is only {c['accuracy_m']:.0f} m (needs {config.CPV_MAX_ACCURACY_M:.0f} m or better)")
                continue
            if c.get("source") != "camera_stream":
                problems.append(f"the {kind} photo was not captured from the live camera")
            if (c.get("exif") or {}).get("has_camera_exif"):
                problems.append(f"the {kind} photo carries a camera EXIF block, which a live browser capture does not (it may come from a gallery)")
            if c.get("accuracy_m", 9999) > config.CPV_MAX_ACCURACY_M:
                problems.append(f"the {kind} photo's GPS accuracy is only {c['accuracy_m']:.0f} m (needs {config.CPV_MAX_ACCURACY_M:.0f} m or better)")
        apart = geo.haversine_m(ext["lat"], ext["lon"], cnt["lat"], cnt["lon"])
        if apart > SAME_PLACE_M + ext.get("accuracy_m", 0) + cnt.get("accuracy_m", 0):
            problems.append(f"the two photos were taken {apart:.0f} m apart, so they are not from the same premises")
        checks.append(_check("capture_integrity", "Live camera capture, fresh clock, accurate GPS", "fail" if problems else "pass",
                             (lambda t: t[:1].upper() + t[1:])("; ".join(problems)) + "." if problems else
                             f"Both photos came from the live camera with no camera EXIF block, GPS accuracy {ext['accuracy_m']:.0f} m and {cnt['accuracy_m']:.0f} m, "
                             f"{apart:.0f} m apart." + (f" DEMO MODE: the {' and '.join(demo_uploads)} photo(s) were uploaded from a file, not captured live, so the live-capture rules were not applied to them." if demo_uploads else ""),
                             evidence={"exterior": {k: ext[k] for k in ("lat", "lon", "accuracy_m", "heading", "client_ts")},
                                       "counter": {k: cnt[k] for k in ("lat", "lon", "accuracy_m", "heading", "client_ts")}}))

        # 2 signboard name ------------------------------------------------------------------
        trade, trade_src = _trade_name(db, case)
        ocr_ext = ocr_cnt = ""
        ocr_error = None
        try:
            ocr_ext = _ocr(ext["path"], ext["sha256"])
        except Exception as e:  # noqa: BLE001
            ocr_error = str(e)[:200]
        if ocr_error:
            checks.append(_check("signboard_name", "Signboard shows the trade name", "fail", f"The signboard could not be read ({ocr_error}).", trade_name=trade))
        else:
            latin_ocr = _latin(ocr_ext)                        # a Hindi signboard is compared with an English trade name after transliteration
            trade_latin = _latin(trade)
            seen = " ".join(ocr_ext.split())[:120]
            seen_text = ocr_ext + "\n" + latin_ocr
            candidates = [vision.name_match(trade, seen_text)]
            if trade_latin:
                candidates.append(vision.name_match(trade_latin, seen_text))
            nm = max(candidates, key=lambda m: m["score"])
            full, part = nm["score"] >= 0.99, nm["score"] >= 0.5
            translit = f" (transliterated: “{' '.join(latin_ocr.split())[:80]}”)" if latin_ocr else ""
            detail = (f"The signboard reads “{seen}”{translit} and contains {', '.join(nm['found']) or 'none'} of the trade name “{trade}” "
                      f"(from the {trade_src})." + (f" Missing: {', '.join(nm['missing'])}." if nm["missing"] else "") + (f" {nm['note']}" if nm.get("note") and not full else ""))
            checks.append(_check("signboard_name", "Signboard shows the trade name", "pass" if full else "fail", detail, trade_name=trade, score=nm["score"],
                                 partial=part and not full))

        # 3 proximity -----------------------------------------------------------------------
        ref = geo.resolve_reference(db, case)
        dist = None
        if ref["lat"] is None:
            checks.append(_check("proximity", f"Shop is within {config.CPV_RADIUS_M:.0f} m of the declared address", "fail",
                                 f"There is no reference point to measure from. {ref.get('note') or ''}".strip(), reference=ref))
        else:
            dist = geo.haversine_m(ext["lat"], ext["lon"], ref["lat"], ref["lon"])
            reliable = ref.get("precision") != "coarse"
            ok = dist <= config.CPV_RADIUS_M and reliable
            why = ("" if reliable else " The reference came from an area-level match, so this distance is not reliable.")
            checks.append(_check("proximity", f"Shop is within {config.CPV_RADIUS_M:.0f} m of the declared address", "pass" if ok else "fail",
                                 f"The exterior photo was taken {dist:.0f} m from the declared address ({ref['address_source']}: “{ref['address']}”; reference: {ref['source']}).{why}"
                                 + (f" {ref['note']}" if ref.get("note") else ""), distance_m=round(dist, 1), reference=ref))

        # 4 screen replay -------------------------------------------------------------------
        scores = {}
        for kind in REQUIRED:
            try:
                scores[kind] = vision.replay_score(Path(s.captures[kind]["path"]).read_bytes())
            except Exception as e:  # noqa: BLE001
                scores[kind] = {"score": 1.0, "note": f"could not be analysed ({e})"}
        worst = max(v["score"] for v in scores.values())
        checks.append(_check("screen_replay", "Photos are not pictures of a screen or a print", "fail" if worst >= vision.REPLAY_FLAG_AT else "pass",
                             ("A regular pixel pattern typical of a photographed screen was found" if worst >= vision.REPLAY_FLAG_AT else "No screen-replay pattern was found")
                             + f" (exterior {scores['exterior']['score']:.2f}, counter {scores['counter']['score']:.2f}; flag at {vision.REPLAY_FLAG_AT}). Heuristic check: a person decides.",
                             scores=scores, assistive=True))

        # 5 MCC / inventory (soft) ----------------------------------------------------------
        mcc = vision.mcc_for(case.mcc, case.industry)
        try:
            ocr_cnt = _ocr(cnt["path"], cnt["sha256"])
        except Exception as e:  # noqa: BLE001
            ocr_cnt = ""
            mc = {"status": "warn", "label": None, "found": [], "note": f"The counter photo could not be read ({str(e)[:120]})."}
        else:
            mc = vision.mcc_match(mcc, ocr_cnt)
        checks.append(_check("mcc_inventory", f"Counter fits the declared category{f' (MCC {mcc})' if mcc else ''}", mc["status"],
                             (f"Read on the counter photo: {', '.join(mc['found'])}. These fit {mc['label']}." if mc["status"] == "pass" else mc.get("note") or ""),
                             assistive=True, soft=True, mcc=mcc))

        hard_ok = all(c["status"] == "pass" for c in checks if not c.get("soft"))
        verdict = VERDICT_VERIFIED if hard_ok else VERDICT_REVIEW
        failed = [c["label"] for c in checks if not c.get("soft") and c["status"] != "pass"]
        demo_note = " DEMO MODE: some photos were uploaded from a file, not captured live." if demo_uploads else ""
        summary = ("Drishti verified the shop: the signboard shows the trade name, the photos were taken "
                   f"{dist:.0f} m from the declared address, and the capture looks live."
                   + (" The counter photo did not clearly match the declared category; see the note." if checks[-1]["status"] == "warn" else "")
                   + demo_note) if hard_ok else ("A person needs to look: " + "; ".join(failed) + "." + demo_note)
        s.result = {"verdict": verdict, "summary": summary, "checks": checks, "distance_m": round(dist, 1) if dist is not None else None,
                    "reference": ref, "trade_name": trade,
                    "ocr": {"exterior": " ".join(ocr_ext.split())[:600], "counter": " ".join(ocr_cnt.split())[:600]},
                    "analysed_at": utcnow().isoformat()}
        s.status, s.updated_at = ("verified" if hard_ok else "needs_review"), utcnow()
        db.add(s)
        db.commit()

        for c in checks:
            if c["status"] in {"fail", "warn"}:
                audit(db, case.id, "agent", f"Drishti: {c['label']}", c["detail"][:300], "warning")
        if hard_ok:
            if case.stage == STAGE_CPV:
                case.stage, case.status = STAGE_VCIP, "ready_for_review"
                db.add(case)
                db.commit()
            audit(db, case.id, "agent", f"Drishti verified the shop · {VERDICT_VERIFIED}", summary, "success")
            from app import vcip
            vcip.ensure(db, case)
        else:
            case.status = "needs_attention"
            db.add(case)
            db.commit()
            audit(db, case.id, "agent", f"Drishti needs a person to review · {VERDICT_REVIEW}", summary, "warning")
        return s.result


def memory_summary(session: Session, case: Case, s: CpvSession) -> dict:
    """The text n8n stores in the case's Cognee dataset, so 'Ask this case' can answer questions about the shop verification."""
    r = s.result or {}
    lines = [f"Contact point verification (shop visit by photo) for {case.legal_name}, case {case.id}.",
             f"Verdict: {r.get('verdict', 'not analysed yet')}. {r.get('summary', '')}".strip()]
    for c in r.get("checks", []):
        lines.append(f"- {c['label']}: {c['status'].upper()}. {c['detail']}")
    ref = r.get("reference") or {}
    if r.get("distance_m") is not None:
        lines.append(f"The exterior photo was taken {r['distance_m']:.0f} m from the declared address ({ref.get('address_source')}).")
    if (r.get("ocr") or {}).get("exterior"):
        lines.append(f"Text read on the signboard: {r['ocr']['exterior']}")
    if s.decided_by:
        lines.append(f"A person ({s.decided_by}) reviewed and decided this verification.")
    return {"case_id": case.id, "session_id": s.id, "dataset": f"case_{case.slug}", "file_prefix": f"cpv-{s.id}", "text": "\n".join(lines)}


# ---------------------------------------------------------------- views
def view(s: CpvSession | None) -> dict | None:
    if s is None:
        return None
    caps = {k: {"lat": v["lat"], "lon": v["lon"], "accuracy_m": v["accuracy_m"], "heading": v.get("heading"), "client_ts": v["client_ts"],
                "width": v["width"], "height": v["height"]} for k, v in (s.captures or {}).items()}
    r = s.result or {}
    return {"status": s.status, "link": link_for(s) if s.status in {"waiting", "captured"} else None, "expiresAt": _aware(s.expires_at).isoformat(),
            "required": list(REQUIRED), "optional": list(OPTIONAL), "captured": caps, "verdict": r.get("verdict"), "summary": r.get("summary"),
            "checks": r.get("checks", []), "distanceM": r.get("distance_m"), "reference": r.get("reference"), "tradeName": r.get("trade_name"),
            "ocr": r.get("ocr"), "decidedBy": s.decided_by, "sessionId": s.id}
