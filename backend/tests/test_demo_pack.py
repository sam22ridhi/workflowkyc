"""The realistic demo pack: deterministic bytes (so recorded Sarvam results keep matching), every document recorded, all watermarked specimens."""
import hashlib
from pathlib import Path

from app.doctypes import guess_doc_type
from seed.make_realistic_docs import CORRECT_PACK, FIX_PACK, PACK, generate, generate_correct, generate_fixes

BACKEND = Path(__file__).resolve().parent.parent
CACHE = BACKEND / "demo_cache"
PACK_DIR = BACKEND / "seed" / "demo_pack"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_generation_is_byte_for_byte_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        generate(out)
        generate_fixes(out / "fixes")
        generate_correct(out / "correct")
    for name in list(PACK) + [f"correct/{n}" for n in CORRECT_PACK] + [f"fixes/{n}" for n in FIX_PACK]:
        assert sha(a / name) == sha(b / name), name


def test_the_pack_is_nine_documents_the_fixes_four_and_the_correct_set_twelve():
    assert len(PACK) == 9 and len(FIX_PACK) == 4 and len(CORRECT_PACK) == 12


def test_the_committed_pack_matches_what_the_generator_makes(tmp_path):
    """If this fails the generator changed: the recorded Sarvam results (keyed by file hash) no longer match the files. Regenerate with seed.bat --refresh-cache."""
    generate(tmp_path)
    for name in PACK:
        if (PACK_DIR / name).exists():
            assert sha(PACK_DIR / name) == sha(tmp_path / name), f"{name} differs from the generator output"


def test_every_pack_document_has_a_recorded_sarvam_result():
    """What lets the demo run with DEMO_MODE=true when the network or the Sarvam credit fails."""
    missing = []
    for name in PACK:
        p = PACK_DIR / name
        if not p.exists():
            continue
        h = sha(p)
        if not ((CACHE / f"{h}.digitise.json").exists() and any(CACHE.glob(f"{h}.extract-*.json"))):
            missing.append(name)
    assert not missing, f"no recorded Sarvam result for {missing}: run seed.bat --refresh-cache (needs Sarvam credit)"


def test_filenames_are_classified_without_help():
    expected = {"01_Company_PAN.pdf": "pan", "02_GST_Certificate.pdf": "gst", "03_Certificate_of_Incorporation.pdf": "coi", "04_Board_Resolution.pdf": "board_resolution",
                "05_Cancelled_Cheque.pdf": "bank_cheque", "06_Director_KYC_Anil_Sharma.pdf": "director_kyc", "07_Shareholding_Declaration.pdf": "shareholding",
                "08_FSSAI_Licence.pdf": "fssai", "09_Electricity_Bill.pdf": "electricity_bill"}
    for name, kind in expected.items():
        assert guess_doc_type(name) == kind, name
    for name in ("F1_Cancelled_Cheque_CORRECTED.pdf", "F2_Director_KYC_Priya_Sharma.pdf", "F3_Owner_KYC_Rakesh_Sharma.pdf", "F4_Owner_KYC_Meera_Sharma.pdf"):
        assert guess_doc_type(name) in {"bank_cheque", "director_kyc"}, name


def test_every_document_says_it_is_a_specimen(tmp_path):
    generate(tmp_path)
    generate_fixes(tmp_path / "fixes")
    for p in list(tmp_path.glob("*.pdf")) + list((tmp_path / "fixes").glob("*.pdf")):
        raw = p.read_bytes()
        assert raw.startswith(b"%PDF") and len(raw) > 2000
    # the watermark and footer are drawn on every page by the generator (see specimen()); guard against removal
    src = (BACKEND / "seed" / "make_realistic_docs.py").read_text(encoding="utf-8")
    assert src.count("specimen(c)") >= 9 and "SPECIMEN - SYNTHETIC DEMO DATA" in src and "Not a valid document" in src
