"""Where the shop should be, and how far the photo is from it.

haversine_m()        great-circle distance between two points in metres
geocode()            address -> (lat, lon) through OpenStreetMap Nominatim (free; coarse for many Indian addresses)
resolve_reference()  the reference point for a case: a confirmed pin or demo reference, else the geocoded address
                     (electricity-bill address first, then the GST principal place, then the application address)
"""
import math

import httpx
from sqlmodel import Session

from app.models import Case, Document

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Karyakarta-Drishti/1.0 (merchant onboarding prototype; contact: team Genesis51)"
EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def geocode(address: str) -> dict | None:
    """{lat, lon, display, precision} or None. Nominatim's usage policy: identify the app, at most one request a second, cache results."""
    if not address or not address.strip():
        return None
    try:
        r = httpx.get(NOMINATIM, params={"q": address, "format": "jsonv2", "limit": 1, "countrycodes": "in", "addressdetails": 1},
                      headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
        hits = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not hits:
        return None
    h = hits[0]
    # 'place_rank' >= 26 is street level or finer; anything coarser (city, pincode) cannot support a 100 m check
    precise = int(h.get("place_rank") or 0) >= 26
    return {"lat": float(h["lat"]), "lon": float(h["lon"]), "display": h.get("display_name", ""), "precision": "street" if precise else "coarse"}


def declared_address(session: Session, case: Case) -> tuple[str | None, str]:
    """The address the shop must be at, and where it came from."""
    from sqlmodel import select
    bills = [d for d in session.exec(select(Document).where(Document.case_id == case.id, Document.doc_type == "electricity_bill"))
             if d.fields and (d.fields.get("service_address") or {}).get("value")]
    if bills:
        newest = sorted(bills, key=lambda d: d.created_at)[-1]
        return newest.fields["service_address"]["value"], "electricity bill"
    gst = [d for d in session.exec(select(Document).where(Document.case_id == case.id, Document.doc_type == "gst"))
           if d.fields and (d.fields.get("principal_place_address") or {}).get("value")]
    if gst:
        return sorted(gst, key=lambda d: d.created_at)[-1].fields["principal_place_address"]["value"], "GST certificate (principal place)"
    return (case.operating_address or case.registered_address), "merchant application"


def resolve_reference(session: Session, case: Case) -> dict:
    """{lat, lon, source, address, address_source, precision?, note?}. lat/lon are None when no reference could be established."""
    address, address_source = declared_address(session, case)
    if case.ref_lat is not None and case.ref_lon is not None and case.ref_source in {"demo", "pin"}:
        return {"lat": case.ref_lat, "lon": case.ref_lon, "source": case.ref_source, "address": case.ref_label or address, "address_source": address_source,
                "note": "Demo reference point set by the team, not a geocoded address." if case.ref_source == "demo" else "Location pin confirmed by the merchant."}
    if case.ref_lat is not None and case.ref_source == "osm" and case.ref_label == address:
        return {"lat": case.ref_lat, "lon": case.ref_lon, "source": "osm", "address": address, "address_source": address_source, "precision": "cached"}
    if not address:
        return {"lat": None, "lon": None, "source": None, "address": None, "address_source": address_source, "note": "No address on file to measure against."}
    hit = geocode(address)
    if not hit:
        return {"lat": None, "lon": None, "source": None, "address": address, "address_source": address_source,
                "note": "The address could not be turned into coordinates."}
    case.ref_lat, case.ref_lon, case.ref_source, case.ref_label = hit["lat"], hit["lon"], "osm", address
    session.add(case)
    session.commit()
    out = {"lat": hit["lat"], "lon": hit["lon"], "source": "osm", "address": address, "address_source": address_source, "precision": hit["precision"]}
    if hit["precision"] == "coarse":
        out["note"] = "OpenStreetMap only found this address at area level, so a 100 m check is not reliable."
    return out
