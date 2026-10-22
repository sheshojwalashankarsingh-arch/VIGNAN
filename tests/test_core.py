"""
Run with:  python -m pytest -q
Uses a temporary data folder, so it never touches your real database.
"""

import os
import sys
import tempfile

os.environ["VIGNAN_DATA_DIR"] = tempfile.mkdtemp()
os.environ["VIGNAN_DISABLE_EMBEDDINGS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf  # noqa: E402

import db  # noqa: E402
import ingest  # noqa: E402
import llm  # noqa: E402
import search  # noqa: E402
import syllabus  # noqa: E402
import seed_demo  # noqa: E402

seed_demo.main()
NA, PY = 1, 2


def test_login():
    assert db.login("student", "student123")["role"] == "student"
    assert db.login("student", "wrong") is None


def test_search_finds_right_page():
    top = search.search([NA], "Thevenin's theorem", k=1)[0]
    assert top["resource_title"] == "Network Theory Lecture Notes" and top["page"] == 5
    top = search.search([NA], "voltage around a closed loop", k=1)[0]
    assert top["page"] == 2


def test_search_respects_subject():
    hits = search.search([PY], "Thevenin theorem")
    assert all(h["subject_id"] == PY for h in hits)


def test_syllabus_units():
    units = syllabus.units_for_subject(NA)
    assert [u["unit"] for u in units] == ["UNIT I", "UNIT II", "UNIT III", "UNIT IV", "UNIT V"]
    assert "Thevenin's theorem" in units[1]["topics"]


def test_parse_units_inline_format():
    text = "UNIT-1: Basics: Ohm's law, KCL (6 hours)\nUNIT-2 Theorems\nThevenin\nNorton\nTEXT BOOKS\n1. X"
    units = syllabus.parse_units(text)
    assert units[0]["title"] == "Basics" and units[0]["topics"] == ["Ohm's law", "KCL"]
    assert units[1]["topics"] == ["Thevenin", "Norton"]


def test_offline_answer_has_citations():
    hits = search.search([NA], "time constant of RC circuit")
    text, provider = llm.answer("time constant of RC circuit", hits)
    assert provider == "offline" and "[1]" in text


def test_scanned_pdf_detected():
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()           # blank pages = no text layer, like a scan
    data = doc.tobytes()
    rep = ingest.add_pdf(NA, "Scan", "other", "scan.pdf", data, None)
    assert rep["looks_scanned"]
    db.delete_resource(rep["resource_id"])
    assert db.get_resource(rep["resource_id"]) is None
