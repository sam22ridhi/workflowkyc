"""Step 1: talk to Sarvam directly, no FastAPI, no n8n.

Run from the project root:
    python scripts/test_sarvam_pan.py samples/pan_sharma_foods.png

It prints Sarvam's RAW result so you can see the exact JSON shape once,
then the rule checks.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import sarvam_client  # noqa: E402
from app.main import pick_fields  # noqa: E402
from app.schemas import PAN_SCHEMA  # noqa: E402
from app.validators import check_pan, summarise  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else "samples/pan_sharma_foods.png"
print(f"Sending {path} to Sarvam Document Intelligence (extract)...")
out = sarvam_client.extract(path, PAN_SCHEMA)
print(f"\njob {out['job_id']} -> {out['status']} in {out['seconds']}s")
print("\n--- RAW RESULT ---")
print(json.dumps(out["raw"], indent=2, default=str))

fields, confidence = pick_fields(out["raw"], PAN_SCHEMA)
print("\n--- FIELDS ---")
print(json.dumps(fields, indent=2))
print("confidence:", confidence)

checks = check_pan(fields, declared_entity_type="private_limited",
                   declared_name="Sharma Foods Private Limited")
print("\n--- CHECKS ---")
for c in checks:
    print(f"[{c['status'].upper():4}] {c['label']}: {c['detail']}")
print("\nOverall:", summarise(checks))
