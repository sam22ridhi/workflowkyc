"""Contact point verification end to end: link, capture rules, Drishti's checks, verdict, stages and the human guards.
Sarvam (signboard OCR) and geocoding are mocked; images are synthetic. Nothing leaves the machine."""
import time

import numpy as np
import pytest
from PIL import Image
from sqlmodel import Session, select

from app import config
from app.db import engine
from app.drishti import geo, service
from app.models import Case, CpvSession
from tests.test_drishti_vision import _jpeg, _scene

CASE = "KYB-20817"
HERE = (19.0760, 72.8777)
TEXTS = {"exterior": "SHARMA FOODS\nRoyal Rajasthan Spices\nPure Veg", "counter": "MENU\nMasala Chai 20\nVeg Thali 120\nScan to pay"}


def photo(seed=1):
    return _jpeg(_scene(seed, 800, 600))


def post_capture(client, token, kind, image=None, *, lat=HERE[0], lon=HERE[1], accuracy=12, ts=None, source="camera_stream", heading="87"):
    return client.post(f"/api/cpv/{token}/capture", data={"kind": kind, "lat": lat, "lon": lon, "accuracy_m": accuracy, "heading": heading,
                                                           "client_ts": str(ts if ts is not None else int(time.time() * 1000)), "source": source},
                       files={"image": (f"{kind}.jpg", image if image is not None else photo(), "image/jpeg")})


@pytest.fixture
def cpv(client, monkeypatch):
    """Open contact point verification on a clean case (stage 6 via Compliance), with OCR and the reference point controlled."""
    monkeypatch.setattr(config, "CPV_ALLOW_DEMO_REFERENCE", True)
    monkeypatch.setattr(config, "CPV_MAX_ACCURACY_M", 100.0)                                   # the user's .env may loosen this for a laptop demo
    monkeypatch.setattr(config, "N8N_CPV_WEBHOOK_URL", "")
    ocr = dict(TEXTS)
    monkeypatch.setattr(service, "_ocr", lambda path, sha: ocr["exterior" if "exterior" in path else "counter"])
    monkeypatch.setattr(service, "_latin", lambda text: "")                                   # no transliteration unless a test enables it
    with Session(engine) as s:
        for row in s.exec(select(CpvSession).where(CpvSession.case_id == CASE)):
            s.delete(row)
        case = s.get(Case, CASE)
        case.stage, case.status, case.route, case.ref_lat, case.ref_lon, case.ref_source = 5, "ready_for_review", "ASK", None, None, None
        case.mcc = "5812"
        s.add(case)
        s.commit()
    assert client.post(f"/api/cases/{CASE}/action", json={"action": "compliance_approve", "actor": "compliance"}).status_code == 200
    assert client.post(f"/api/cases/{CASE}/cpv/demo-reference", json={"lat": HERE[0], "lon": HERE[1], "label": "test shop"}).status_code == 200
    link = client.get(f"/api/cases/{CASE}/cpv").json()["data"]
    token = link["link"].rsplit("/", 1)[1]
    yield {"token": token, "ocr": ocr, "client": client}
    with Session(engine) as s:
        for row in s.exec(select(CpvSession).where(CpvSession.case_id == CASE)):
            s.delete(row)
        case = s.get(Case, CASE)
        case.stage, case.status, case.ref_lat, case.ref_lon, case.ref_source = 2, "docs_pending", None, None, None
        s.add(case)
        s.commit()


def capture_both(client, token, **kw):
    assert post_capture(client, token, "exterior", photo(1), **kw).status_code == 200
    assert post_capture(client, token, "counter", photo(2), **kw).status_code == 200
    return client.post(f"/api/cpv/{token}/submit")


def case_state(client):
    return client.get(f"/api/cases/{CASE}").json()["data"]


# ---------------------------------------------------------------- opening, link and token rules
def test_compliance_approval_opens_verification_and_creates_the_link(cpv):
    c = case_state(cpv["client"])
    assert c["stage"] == 6 and [s["status"] for s in c["stages"]].count("current") == 1 and c["stages"][5]["label"] == "Contact Point Verification"
    assert len(c["stages"]) == 10 and c["status"] == "awaiting_merchant"
    link = c["cpv"]
    assert link["status"] == "waiting" and link["link"] == f"{config.PUBLIC_APP_URL}/cpv/{cpv['token']}" and link["required"] == ["exterior", "counter"]
    assert "Shop verification link ready" in [t["title"] for t in c["timeline"]]
    assert len(cpv["token"]) >= 30                                                           # unguessable


def test_public_capture_state_is_minimal_and_tokens_are_enforced(cpv):
    client = cpv["client"]
    d = client.get(f"/api/cpv/{cpv['token']}").json()["data"]
    assert set(d) == {"merchantName", "status", "required", "optional", "captured", "expiresAt", "verdict", "summary", "maxAccuracyM", "demoUpload"}
    assert client.get("/api/cpv/not-a-real-token").status_code == 404
    with Session(engine) as s:                                                              # an expired link
        row = s.exec(select(CpvSession).where(CpvSession.token == cpv["token"])).one()
        row.expires_at = row.created_at.replace(year=2020)
        s.add(row)
        s.commit()
    r = client.get(f"/api/cpv/{cpv['token']}")
    assert r.status_code == 410 and "expired" in r.json()["detail"]


def test_capture_rules_reject_spoofable_or_unusable_photos(cpv):
    client, t = cpv["client"], cpv["token"]
    bad = post_capture(client, t, "exterior", b"GIF89a....")
    assert bad.status_code == 422 and "JPEG" in bad.json()["detail"]
    tiny = post_capture(client, t, "exterior", _jpeg(np.zeros((100, 100))))
    assert tiny.status_code == 422 and "too small" in tiny.json()["detail"]
    assert post_capture(client, t, "exterior", ts=int(time.time() * 1000) - 600_000).json()["detail"].startswith("The photo's time does not match")
    assert "not valid" in post_capture(client, t, "exterior", lat=0, lon=0).json()["detail"]
    assert post_capture(client, t, "storefront").status_code == 422                          # unknown kind
    assert client.post(f"/api/cpv/{t}/submit").status_code == 422                            # nothing captured yet
    assert post_capture(client, t, "exterior").status_code == 200
    assert "counter" in client.post(f"/api/cpv/{t}/submit").json()["detail"]                 # one photo is not enough
    # no gallery picker exists server-side either: the file field is the only input and it must be a fresh camera frame (checked above)
    for _ in range(12):
        post_capture(client, t, "exterior")
    assert post_capture(client, t, "exterior").status_code == 429                            # rate limit per link


# ---------------------------------------------------------------- the verdict
def test_clean_capture_is_verified_autonomously_and_advances_the_case(cpv):
    client = cpv["client"]
    assert capture_both(client, cpv["token"]).status_code == 200
    # the background task runs in-process when n8n is not configured (TestClient runs it before returning)
    c = case_state(client)
    assert c["cpv"]["status"] == "verified" and c["cpv"]["verdict"] == "CPV_VERIFIED" and c["stage"] == 7
    by_id = {x["id"]: x for x in c["cpv"]["checks"]}
    assert set(by_id) == {"capture_integrity", "signboard_name", "proximity", "screen_replay", "mcc_inventory"}
    assert all(x["status"] == "pass" for x in by_id.values()), {k: v["detail"] for k, v in by_id.items() if v["status"] != "pass"}
    assert c["cpv"]["distanceM"] == 0.0 and "test shop" in by_id["proximity"]["detail"] and "demo" in by_id["proximity"]["detail"].lower()
    assert by_id["signboard_name"]["trade_name"] == "Royal Rajasthan Spices"
    titles = [t["title"] for t in c["timeline"]]
    assert "Drishti verified the shop · CPV_VERIFIED" in titles and titles.index("Shop photos submitted") < titles.index("Drishti verified the shop · CPV_VERIFIED")
    assert c["cpv"]["link"] is None                                                           # a finished session no longer offers the link


def test_drishti_never_fails_a_shop_on_its_own_it_asks_a_person(cpv):
    client = cpv["client"]
    # photographed 300 m from the declared address
    capture_both(client, cpv["token"], lat=HERE[0] + 0.0027)
    c = case_state(client)
    assert c["cpv"]["status"] == "needs_review" and c["cpv"]["verdict"] == "NEEDS_REVIEW" and c["stage"] == 6 and c["status"] == "needs_attention"
    prox = next(x for x in c["cpv"]["checks"] if x["id"] == "proximity")
    assert prox["status"] == "fail" and 280 < prox["distance_m"] < 320 and "300 m" in prox["detail"].replace("299", "300").replace("301", "300")
    assert c["cpv"]["summary"].startswith("A person needs to look:")
    assert "Drishti needs a person to review · NEEDS_REVIEW" in [t["title"] for t in c["timeline"]]


@pytest.mark.parametrize("change,failing", [
    ({"ocr": "Royal Traders"}, "signboard_name"),
    ({"accuracy": 400}, "capture_integrity"),
    ({"source": "file_picker"}, "capture_integrity"),
])
def test_each_hard_check_can_send_the_case_to_a_person(cpv, change, failing):
    client = cpv["client"]
    if "ocr" in change:
        cpv["ocr"]["exterior"] = change["ocr"]
        kw = {}
    else:
        kw = {k: v for k, v in change.items()}
    capture_both(client, cpv["token"], **kw)
    c = case_state(client)
    assert c["cpv"]["status"] == "needs_review"
    assert {x["id"]: x["status"] for x in c["cpv"]["checks"]}[failing] == "fail"


def test_a_hindi_signboard_is_matched_to_an_english_trade_name_through_transliteration(cpv, monkeypatch):
    client = cpv["client"]
    cpv["ocr"]["exterior"] = "रॉयल राजस्थान स्पाइसेस"                                         # what Sarvam reads from a Devanagari sign
    monkeypatch.setattr(service, "_latin", lambda text: "Royal Rajasthan Spices" if "रॉयल" in text else "")
    capture_both(client, cpv["token"])
    sign = next(x for x in case_state(client)["cpv"]["checks"] if x["id"] == "signboard_name")
    assert sign["status"] == "pass" and "transliterated: “Royal Rajasthan Spices”" in sign["detail"] and sign["score"] == 1.0


def test_a_hindi_signboard_without_transliteration_still_goes_to_a_person_with_the_reason(cpv):
    client = cpv["client"]
    cpv["ocr"]["exterior"] = "रॉयल राजस्थान स्पाइसेस"
    capture_both(client, cpv["token"])
    sign = next(x for x in case_state(client)["cpv"]["checks"] if x["id"] == "signboard_name")
    assert sign["status"] == "fail" and "does not transliterate" in sign["detail"]


def test_a_gallery_photo_with_camera_exif_is_flagged(cpv):
    client = cpv["client"]
    exif = Image.Exif()
    exif[271], exif[272] = "Samsung", "SM-A546"
    assert post_capture(client, cpv["token"], "exterior", _jpeg(_scene(3, 800, 600), exif=exif.tobytes())).status_code == 200
    assert post_capture(client, cpv["token"], "counter", photo(2)).status_code == 200
    client.post(f"/api/cpv/{cpv['token']}/submit")
    integrity = next(x for x in case_state(client)["cpv"]["checks"] if x["id"] == "capture_integrity")
    assert integrity["status"] == "fail" and "EXIF" in integrity["detail"]


def test_two_photos_taken_in_different_places_are_flagged(cpv):
    client, t = cpv["client"], cpv["token"]
    post_capture(client, t, "exterior")
    post_capture(client, t, "counter", lat=HERE[0] + 0.01)                                    # about 1.1 km away
    client.post(f"/api/cpv/{t}/submit")
    integrity = next(x for x in case_state(client)["cpv"]["checks"] if x["id"] == "capture_integrity")
    assert integrity["status"] == "fail" and "not from the same premises" in integrity["detail"]


def test_a_photo_of_a_screen_is_flagged_but_the_mcc_check_is_only_a_note(cpv):
    client, t = cpv["client"], cpv["token"]
    yy, xx = np.indices((720, 1000))
    screen = _scene(5, 1000, 720) + 12 * np.sin(2 * np.pi * xx / 4) * np.sin(2 * np.pi * yy / 4) + 7 * np.sin(2 * np.pi * (xx * 0.93 + yy * 0.31) / 5.3)
    post_capture(client, t, "exterior", _jpeg(screen))
    post_capture(client, t, "counter", photo(2))
    client.post(f"/api/cpv/{t}/submit")
    ids = {x["id"]: x for x in case_state(client)["cpv"]["checks"]}
    assert ids["screen_replay"]["status"] == "fail" and ids["screen_replay"]["assistive"]
    # MCC mismatch alone does not stop an otherwise clean verification
    cpv["ocr"]["counter"] = "Mobile Charger Laptop"
    cpv["ocr"]["exterior"] = TEXTS["exterior"]
    client.post(f"/api/cases/{CASE}/cpv/link")                                                # (current session stays; use a fresh one below)
    client.post(f"/api/cases/{CASE}/action", json={"action": "cpv_retake", "actor": "kam"})
    t2 = client.get(f"/api/cases/{CASE}/cpv").json()["data"]["link"].rsplit("/", 1)[1]
    capture_both(client, t2)
    c = case_state(client)
    mcc = next(x for x in c["cpv"]["checks"] if x["id"] == "mcc_inventory")
    assert mcc["status"] == "warn" and mcc.get("soft") and c["cpv"]["verdict"] == "CPV_VERIFIED" and "did not clearly match the declared category" in c["cpv"]["summary"]


# ---------------------------------------------------------------- people decide
def test_kam_can_approve_a_flagged_verification_and_the_agent_cannot(cpv):
    client = cpv["client"]
    capture_both(client, cpv["token"], lat=HERE[0] + 0.0027)
    for actor in ("agent", "merchant", "compliance"):
        r = client.post(f"/api/cases/{CASE}/action", json={"action": "cpv_approve", "actor": actor})
        assert r.status_code == 403, actor
    r = client.post(f"/api/cases/{CASE}/action", json={"action": "cpv_approve", "actor": "kam"})
    assert r.status_code == 200 and r.json()["data"]["stage"] == 7
    assert client.get(f"/api/cases/{CASE}/cpv").json()["data"]["decidedBy"] == "kam"
    assert client.post(f"/api/cases/{CASE}/action", json={"action": "cpv_approve", "actor": "kam"}).status_code == 409     # stage moved on


def test_nothing_to_approve_before_drishti_flags_something_and_stage_guards_hold(cpv):
    client = cpv["client"]
    r = client.post(f"/api/cases/{CASE}/action", json={"action": "cpv_approve", "actor": "kam"})
    assert r.status_code == 409 and "nothing to approve" in r.json()["detail"]
    assert client.post(f"/api/cases/{CASE}/action", json={"action": "vcip_signoff", "actor": "compliance"}).status_code == 409   # stage 7 not reached
    assert client.post(f"/api/cases/KYB-20815/action", json={"action": "cpv_retake", "actor": "kam"}).status_code == 409          # that case is not at stage 6


def test_retake_replaces_the_link(cpv):
    client = cpv["client"]
    old = cpv["token"]
    r = client.post(f"/api/cases/{CASE}/action", json={"action": "cpv_retake", "actor": "kam"})
    assert r.status_code == 200
    new = client.get(f"/api/cases/{CASE}/cpv").json()["data"]["link"].rsplit("/", 1)[1]
    assert new != old and client.get(f"/api/cpv/{old}").status_code == 410 and client.get(f"/api/cpv/{new}").status_code == 200


def test_demo_reference_is_off_unless_enabled(cpv, monkeypatch):
    monkeypatch.setattr(config, "CPV_ALLOW_DEMO_REFERENCE", False)
    r = cpv["client"].post(f"/api/cases/{CASE}/cpv/demo-reference", json={"lat": 1, "lon": 2})
    assert r.status_code == 403 and "CPV_ALLOW_DEMO_REFERENCE" in r.json()["detail"]


def test_evidence_images_are_served_to_the_case_view(cpv):
    client = cpv["client"]
    post_capture(client, cpv["token"], "exterior")
    r = client.get(f"/api/cases/{CASE}/cpv/images/exterior")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:3] == b"\xff\xd8\xff"
    assert client.get(f"/api/cases/{CASE}/cpv/images/counter").status_code == 404


# ---------------------------------------------------------------- geography
def test_reference_uses_a_pin_or_demo_point_else_geocodes_and_flags_coarse_matches(client, monkeypatch):
    with Session(engine) as s:
        case = s.get(Case, CASE)
        case.ref_lat = case.ref_lon = case.ref_source = case.ref_label = None
        s.add(case)
        s.commit()
        monkeypatch.setattr(geo, "geocode", lambda addr: {"lat": 19.0, "lon": 72.9, "display": "x", "precision": "coarse"})
        ref = geo.resolve_reference(s, case)
        assert ref["source"] == "osm" and ref["precision"] == "coarse" and "not reliable" in ref["note"]
        monkeypatch.setattr(geo, "geocode", lambda addr: None)
        case.ref_lat = case.ref_lon = case.ref_source = case.ref_label = None
        assert geo.resolve_reference(s, case)["lat"] is None
        case.ref_lat, case.ref_lon, case.ref_source = 1.0, 2.0, "pin"
        assert geo.resolve_reference(s, case)["source"] == "pin"
        case.ref_lat = case.ref_lon = case.ref_source = case.ref_label = None
        s.add(case)
        s.commit()


def test_nominatim_result_parsing(monkeypatch):
    import httpx

    def fake_get(url, params, headers, timeout):
        assert "Karyakarta-Drishti" in headers["User-Agent"] and params["countrycodes"] == "in"
        return httpx.Response(200, json=[{"lat": "19.0332", "lon": "73.0297", "display_name": "12 MG Road", "place_rank": 30}], request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    assert geo.geocode("12 MG Road, Navi Mumbai") == {"lat": 19.0332, "lon": 73.0297, "display": "12 MG Road", "precision": "street"}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, json=[], request=httpx.Request("GET", "x")))
    assert geo.geocode("nowhere") is None and geo.geocode("   ") is None


def test_verification_evidence_can_be_stored_in_case_memory(cpv):
    client = cpv["client"]
    assert client.get(f"/api/cases/{CASE}/cpv/memory-summary").status_code == 409                # nothing analysed yet
    capture_both(client, cpv["token"], lat=HERE[0] + 0.0027)
    d = client.get(f"/api/cases/{CASE}/cpv/memory-summary").json()["data"]
    assert d["dataset"] == "case_royal_rajasthan" and d["file_prefix"].startswith("cpv-") and "NEEDS_REVIEW" in d["text"]
    assert "Shop is within 100 m of the declared address: FAIL" in d["text"] and "Royal Rajasthan Spices" in d["text"]
    ok = client.post(f"/api/cases/{CASE}/cpv/memory/result", json={"status": "stored"}).json()["data"]
    assert ok["status"] == "stored" and "Shop verification stored in Cognee memory" in [t["title"] for t in case_state(client)["timeline"]]
    client.post(f"/api/cases/{CASE}/cpv/memory/result", json={"status": "failed", "error": "401"})
    assert "Memory unavailable" in [t["title"] for t in case_state(client)["timeline"]]


def test_a_graph_with_only_verification_evidence_is_ready(cpv):
    client = cpv["client"]
    capture_both(client, cpv["token"], lat=HERE[0] + 0.0027)
    assert client.post(f"/api/cases/{CASE}/memory/graph-result", json={"status": "completed"}).json()["data"]["graph_status"] == "none"      # nothing stored yet
    client.post(f"/api/cases/{CASE}/cpv/memory/result", json={"status": "stored"})
    assert client.post(f"/api/cases/{CASE}/memory/graph-result", json={"status": "completed"}).json()["data"]["graph_status"] == "ready"


# ---------------------------------------------------------------- demo upload (labelled, only when the demo flag is on)
def test_demo_upload_is_refused_unless_the_demo_flag_is_on(cpv, monkeypatch):
    monkeypatch.setattr(config, "CPV_ALLOW_DEMO_REFERENCE", False)
    r = post_capture(cpv["client"], cpv["token"], "exterior", source="demo_upload")
    assert r.status_code == 403 and "disabled" in r.json()["detail"]


def test_demo_upload_works_in_demo_mode_and_says_so(cpv):
    client, t = cpv["client"], cpv["token"]
    assert client.get(f"/api/cpv/{t}").json()["data"]["demoUpload"] is True
    post_capture(client, t, "exterior", source="demo_upload")
    post_capture(client, t, "counter", source="demo_upload")
    client.post(f"/api/cpv/{t}/submit")
    c = case_state(client)["cpv"]
    integrity = next(x for x in c["checks"] if x["id"] == "capture_integrity")
    assert integrity["status"] == "pass" and "DEMO MODE" in integrity["detail"]
    assert "DEMO MODE" in c["summary"]


def test_demo_upload_still_needs_a_precise_enough_location(cpv):
    client, t = cpv["client"], cpv["token"]
    post_capture(client, t, "exterior", source="demo_upload", accuracy=400)
    post_capture(client, t, "counter", source="demo_upload", accuracy=400)
    client.post(f"/api/cpv/{t}/submit")
    integrity = next(x for x in case_state(client)["cpv"]["checks"] if x["id"] == "capture_integrity")
    assert integrity["status"] == "fail" and "GPS accuracy" in integrity["detail"]
