"""
syllabus.py — reads the faculty's syllabus PDF and builds a "Study Map":
for every topic in every unit, which book and which page covers it.

This answers the student's real problem: "what do I study, and where?"
"""

import re

import db
import search
from ingest import extract_pages

UNIT_RE = re.compile(r"\bUNIT\s*[-–—:]?\s*(I{1,3}|IV|V|VI|[1-6])\b\s*[:\-–—.]?\s*", re.IGNORECASE)
STOP_RE = re.compile(r"\b(TEXT\s*BOOKS?|REFERENCE\s*BOOKS?|REFERENCES|COURSE\s*OUTCOMES|SUGGESTED\s*READING)\b",
                     re.IGNORECASE)
ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}


def _clean_topic(t):
    t = re.sub(r"\(\s*\d+\s*(hours?|hrs?|lectures?|periods?)\s*\)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^[\s•\-–*·\d.)]+", "", t)
    return t.strip(" .:;-–")


def parse_units(text):
    """Return [{'unit': 'UNIT I', 'title': ..., 'topics': [...]}, ...]."""
    stop = STOP_RE.search(text)
    if stop:
        text = text[: stop.start()]
    marks = list(UNIT_RE.finditer(text))
    units = []
    for i, m in enumerate(marks):
        body = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip()
        if not body:
            continue
        first, _, rest = body.partition("\n")
        # "Network Theorems: Superposition, Thevenin..." -> title + topics on the same line
        if ":" in first:
            title, _, inline = first.partition(":")
            rest = inline + "\n" + rest
        else:
            title = first
        # topics are usually comma-separated and wrap across lines; if there are no
        # commas at all, treat each line as one topic
        if re.search(r"[,;•]", rest):
            pieces = re.split(r"[,;•]|\s[–-]\s", rest.replace("\n", " "))
        else:
            pieces = rest.split("\n")
        topics = []
        for p in pieces:
            p = _clean_topic(p)
            if 3 <= len(p) <= 90 and p.lower() not in (x.lower() for x in topics):
                topics.append(p)
        units.append({
            "unit": f"UNIT {ROMAN.get(m.group(1), m.group(1).upper())}",
            "title": _clean_topic(title) or "Untitled",
            "topics": topics,
        })
    return units


def units_for_subject(subject_id):
    syl = db.list_resources(subject_id, kind="syllabus")
    if not syl:
        return []
    text = "\n".join(t for _, t in extract_pages(syl[0]["path"]))
    return parse_units(text)


def study_map(subject_id, per_topic=2):
    """For each unit/topic, the best places to read in the uploaded books."""
    units = units_for_subject(subject_id)
    out = []
    for u in units:
        rows, covered = [], 0
        for topic in u["topics"]:
            hits = search.search([subject_id], f"{u['title']} {topic}", k=per_topic)
            # require the topic's own words to appear, so the unit title alone can't match
            topic_words = set(search.tokenize(topic))
            hits = [h for h in hits if topic_words & set(search.tokenize(h["text"]))]
            if hits:
                covered += 1
            rows.append({"topic": topic, "hits": hits})
        out.append({**u, "rows": rows, "covered": covered})
    return out
