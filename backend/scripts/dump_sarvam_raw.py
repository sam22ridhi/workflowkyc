"""Prints REAL raw Sarvam responses (extract AND digitise-json) to debug_out/ so we can see whether
`sources` / digitise output carry page numbers and coordinates. Usage:
    python -m scripts.dump_sarvam_raw seed/sharma_foods/GST_Certificate.pdf gst
"""
import json
import mimetypes
import sys
import time
from pathlib import Path

from app.sarvam import client as sc
from app.sarvam.schemas import SCHEMAS

OUT = Path(__file__).resolve().parent.parent / "debug_out"
OUT.mkdir(exist_ok=True)


def wait(c, job_id):
    t0 = time.time()
    while True:
        st = c.doc_ai.get_status(job_id=job_id)
        status = st.status.lower()
        print(f"  {job_id} {status} ({time.time() - t0:.0f}s)")
        if status in sc.TERMINAL:
            return status, sc._to_dict(st)
        time.sleep(sc.POLL_SECONDS)


def main(path: str, doc_type: str):
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0]
    c = sc.client()
    stem = f"{p.stem}"

    print("extract ...")
    with open(p, "rb") as f:
        job = c.doc_ai.extract(file=[(p.name, f, mime)], schema=json.dumps(SCHEMAS[doc_type]),
                               language="en-IN", output_format="json")
    status, st = wait(c, job.job_id)
    (OUT / f"{stem}.extract.status.json").write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    res = sc._to_dict(c.doc_ai.get_results(job_id=job.job_id))
    (OUT / f"{stem}.extract.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    print("digitise (json) ...")
    with open(p, "rb") as f:
        job = c.doc_ai.digitise(file=[(p.name, f, mime)], language="en-IN", output_format="json")
    status, st = wait(c, job.job_id)
    (OUT / f"{stem}.digitise.status.json").write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    res = sc._to_dict(c.doc_ai.get_results(job_id=job.job_id))
    (OUT / f"{stem}.digitise.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print("wrote", [x.name for x in OUT.glob(stem + '*')])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
