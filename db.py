"""
db.py — everything that touches the SQLite database.

Tables
------
users          faculty / student / admin accounts
classrooms     one per branch + year + section (e.g. "EIE 2nd Year – A")
subjects       a subject inside a classroom, taught by one faculty member
resources      every uploaded file (syllabus, textbook, notes ...)
chunks         small pieces of text cut from each PDF, with page numbers
               -> this is what the AI search actually searches
announcements  short notices a faculty member posts for a subject
"""

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("VIGNAN_DATA_DIR", os.path.join(BASE_DIR, "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "vignan.db")

RESOURCE_KINDS = ["syllabus", "textbook", "notes", "question paper", "other"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS classrooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    branch TEXT NOT NULL,
    year INTEGER NOT NULL,
    section TEXT NOT NULL,
    UNIQUE(branch, year, section)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'faculty', 'student')),
    classroom_id INTEGER REFERENCES classrooms(id)
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT,
    faculty_id INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    pages INTEGER DEFAULT 0,
    text_pages INTEGER DEFAULT 0,
    uploaded_by INTEGER REFERENCES users(id),
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    page INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_subject ON chunks(subject_id);

CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES users(id),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------- connection
def init():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with connect() as con:
        con.executescript(SCHEMA)


@contextmanager
def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return secrets.compare_digest(test.hex(), digest)


# ---------------------------------------------------------------- users
def create_user(username, full_name, password, role, classroom_id=None):
    with connect() as con:
        cur = con.execute(
            "INSERT INTO users (username, full_name, password_hash, role, classroom_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (username.strip().lower(), full_name.strip(), hash_password(password), role, classroom_id),
        )
        return cur.lastrowid


def login(username, password):
    with connect() as con:
        row = con.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip().lower(),)
        ).fetchone()
    if row and check_password(password, row["password_hash"]):
        return dict(row)
    return None


def list_faculty():
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, username, full_name FROM users WHERE role='faculty' ORDER BY full_name")]


def username_exists(username):
    with connect() as con:
        return con.execute("SELECT 1 FROM users WHERE username=?",
                           (username.strip().lower(),)).fetchone() is not None


# ---------------------------------------------------------------- classrooms
def create_classroom(branch, year, section):
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(int(year), "th")
    name = f"{branch.upper()} {year}{suffix} Year – Section {section.upper()}"
    with connect() as con:
        cur = con.execute(
            "INSERT INTO classrooms (name, branch, year, section) VALUES (?, ?, ?, ?)",
            (name, branch.upper(), int(year), section.upper()),
        )
        return cur.lastrowid


def list_classrooms():
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM classrooms ORDER BY branch, year, section")]


def get_classroom(classroom_id):
    with connect() as con:
        r = con.execute("SELECT * FROM classrooms WHERE id=?", (classroom_id,)).fetchone()
        return dict(r) if r else None


# ---------------------------------------------------------------- subjects
def create_subject(classroom_id, name, code, faculty_id):
    with connect() as con:
        cur = con.execute(
            "INSERT INTO subjects (classroom_id, name, code, faculty_id) VALUES (?, ?, ?, ?)",
            (classroom_id, name.strip(), code.strip(), faculty_id),
        )
        return cur.lastrowid


SUBJECT_SELECT = """
SELECT s.*, u.full_name AS faculty_name, c.name AS classroom_name,
       (SELECT COUNT(*) FROM resources r WHERE r.subject_id = s.id) AS resource_count
FROM subjects s
LEFT JOIN users u ON u.id = s.faculty_id
JOIN classrooms c ON c.id = s.classroom_id
"""


def subjects_for_classroom(classroom_id):
    with connect() as con:
        return [dict(r) for r in con.execute(
            SUBJECT_SELECT + " WHERE s.classroom_id=? ORDER BY s.name", (classroom_id,))]


def subjects_for_faculty(faculty_id):
    with connect() as con:
        return [dict(r) for r in con.execute(
            SUBJECT_SELECT + " WHERE s.faculty_id=? ORDER BY c.name, s.name", (faculty_id,))]


def get_subject(subject_id):
    with connect() as con:
        r = con.execute(SUBJECT_SELECT + " WHERE s.id=?", (subject_id,)).fetchone()
        return dict(r) if r else None


# ---------------------------------------------------------------- resources
def add_resource(subject_id, title, kind, filename, path, uploaded_by):
    with connect() as con:
        cur = con.execute(
            "INSERT INTO resources (subject_id, title, kind, filename, path, uploaded_by, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (subject_id, title, kind, filename, path, uploaded_by, _now()),
        )
        return cur.lastrowid


def list_resources(subject_id, kind=None):
    q = "SELECT * FROM resources WHERE subject_id=?"
    args = [subject_id]
    if kind:
        q += " AND kind=?"
        args.append(kind)
    with connect() as con:
        return [dict(r) for r in con.execute(q + " ORDER BY kind, title", args)]


def get_resource(resource_id):
    with connect() as con:
        r = con.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
        return dict(r) if r else None


def delete_resource(resource_id):
    res = get_resource(resource_id)
    if not res:
        return
    with connect() as con:
        con.execute("DELETE FROM resources WHERE id=?", (resource_id,))
    if os.path.exists(res["path"]):
        os.remove(res["path"])


def save_chunks(resource_id, subject_id, chunks, pages, text_pages):
    """chunks = list of (page_number, text)."""
    with connect() as con:
        con.execute("DELETE FROM chunks WHERE resource_id=?", (resource_id,))
        con.executemany(
            "INSERT INTO chunks (resource_id, subject_id, page, text) VALUES (?, ?, ?, ?)",
            [(resource_id, subject_id, p, t) for p, t in chunks],
        )
        con.execute("UPDATE resources SET pages=?, text_pages=? WHERE id=?",
                    (pages, text_pages, resource_id))


def load_chunks(subject_ids):
    """All searchable chunks for the given subjects (syllabus excluded)."""
    if not subject_ids:
        return []
    marks = ",".join("?" * len(subject_ids))
    with connect() as con:
        return [dict(r) for r in con.execute(
            f"""SELECT ch.id, ch.page, ch.text, ch.resource_id, ch.subject_id,
                       r.title AS resource_title, r.kind, s.name AS subject_name
                FROM chunks ch
                JOIN resources r ON r.id = ch.resource_id
                JOIN subjects s ON s.id = ch.subject_id
                WHERE ch.subject_id IN ({marks}) AND r.kind != 'syllabus'
                ORDER BY ch.id""",
            list(subject_ids))]


def chunk_signature(subject_ids):
    """Changes whenever chunks are added/removed — used to know when to rebuild the index."""
    if not subject_ids:
        return "empty"
    marks = ",".join("?" * len(subject_ids))
    with connect() as con:
        r = con.execute(
            f"SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(SUM(id), 0) FROM chunks WHERE subject_id IN ({marks})",
            list(subject_ids)).fetchone()
    return f"{r[0]}-{r[1]}-{r[2]}"


def syllabus_text(subject_id):
    with connect() as con:
        rows = con.execute(
            """SELECT ch.text FROM chunks ch JOIN resources r ON r.id = ch.resource_id
               WHERE ch.subject_id=? AND r.kind='syllabus' ORDER BY ch.id""",
            (subject_id,)).fetchall()
    return "\n".join(r["text"] for r in rows)


# ---------------------------------------------------------------- announcements
def post_announcement(subject_id, author_id, message):
    with connect() as con:
        con.execute(
            "INSERT INTO announcements (subject_id, author_id, message, created_at) VALUES (?, ?, ?, ?)",
            (subject_id, author_id, message.strip(), _now()))


def announcements_for_classroom(classroom_id, limit=20):
    with connect() as con:
        return [dict(r) for r in con.execute(
            """SELECT a.*, s.name AS subject_name, u.full_name AS author
               FROM announcements a JOIN subjects s ON s.id = a.subject_id
               LEFT JOIN users u ON u.id = a.author_id
               WHERE s.classroom_id=? ORDER BY a.id DESC LIMIT ?""",
            (classroom_id, limit))]


def announcements_for_subject(subject_id, limit=20):
    with connect() as con:
        return [dict(r) for r in con.execute(
            """SELECT a.*, u.full_name AS author FROM announcements a
               LEFT JOIN users u ON u.id = a.author_id
               WHERE a.subject_id=? ORDER BY a.id DESC LIMIT ?""",
            (subject_id, limit))]


def delete_announcement(announcement_id):
    with connect() as con:
        con.execute("DELETE FROM announcements WHERE id=?", (announcement_id,))
