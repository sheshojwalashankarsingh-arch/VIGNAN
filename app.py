"""
app.py — the VIGNAN web app (Streamlit).

Run:   streamlit run app.py

Three kinds of users:
  admin    creates classrooms, faculty accounts and subjects
  faculty  uploads syllabus / books / notes for their subjects, posts notices
  student  opens their classroom, asks questions, follows the Study Map,
           reads the exact page the answer came from
"""

import os

import streamlit as st

try:                                   # reads API keys from a .env file, if you made one
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import db
import ingest
import llm
import search
import syllabus

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
EMBLEM = os.path.join(ASSETS, "vnr_emblem.png")

st.set_page_config(page_title="VIGNAN · VNR Learning Platform", page_icon=EMBLEM, layout="wide")

# On Streamlit Cloud, API keys live in "Secrets" — copy them into env vars so llm.py finds them
try:
    for _k in ("GEMINI_API_KEY", "GEMINI_MODEL", "GROQ_API_KEY", "GROQ_MODEL"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

db.init()


@st.cache_resource
def _first_run_setup():
    """Fresh server (e.g. just deployed)? Create the demo college automatically."""
    if not db.username_exists("admin"):
        import seed_demo
        seed_demo.main()
    return True


_first_run_setup()


@st.cache_data
def _b64(path):
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


EMBLEM_SRC = f"data:image/png;base64,{_b64(EMBLEM)}"

# ---------------------------------------------------------------- neon theme
# Palette: black base, deep-navy panels, neon blue glow, VNR orange as a small accent.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Inter:wght@400;500;600&display=swap');
:root {
  --bg: #05070D; --panel: #0C1424; --panel-2: #0F1B33; --line: rgba(46,139,255,.22);
  --neon: #2E8BFF; --neon-2: #00D4FF; --text: #E6EEFF; --muted: #8A9BBD; --vnr: #F5A623;
  --glow: 0 0 6px rgba(46,139,255,.55), 0 0 22px rgba(46,139,255,.25);
}
html, body, .stApp, .stMarkdown, p, li, label, button, input, textarea { font-family: 'Inter', sans-serif; }
/* keep Streamlit's icon font intact (eye icon, arrows, avatars) */
[data-testid="stIconMaterial"], .material-symbols-rounded, span[class*="material"] {
  font-family: 'Material Symbols Rounded' !important;
}

/* background: black with a faint neon grid + blue haze */
.stApp {
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(46,139,255,.18), transparent 60%),
    radial-gradient(900px 400px at -10% 110%, rgba(0,212,255,.10), transparent 60%),
    linear-gradient(rgba(46,139,255,.035) 1px, transparent 1px) 0 0 / 40px 40px,
    linear-gradient(90deg, rgba(46,139,255,.035) 1px, transparent 1px) 0 0 / 40px 40px,
    var(--bg);
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; max-width: 1300px; }

/* headings with neon glow */
h1, h2, h3 { color: var(--text) !important; letter-spacing: .01em; }
h1 { text-shadow: 0 0 18px rgba(46,139,255,.45); }

/* sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #070C18 0%, #05070D 100%);
  border-right: 1px solid var(--line);
  box-shadow: 4px 0 30px rgba(46,139,255,.08);
}

/* buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  background: rgba(12,20,36,.85); color: var(--text);
  border: 1px solid var(--line); border-radius: 10px;
  transition: all .18s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--neon); color: #fff; box-shadow: var(--glow); transform: translateY(-1px);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] {
  background: linear-gradient(90deg, #1F6BFF, #00B4FF); border: none; color: #fff; font-weight: 600;
  box-shadow: var(--glow);
}

/* inputs */
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div, [data-testid="stChatInput"] textarea {
  background: #0A1120 !important; border-color: var(--line) !important; color: var(--text) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus { box-shadow: var(--glow) !important; border-color: var(--neon) !important; }
[data-testid="stChatInput"] { border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 0 24px rgba(46,139,255,.12); }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 8px 14px; }
.stTabs [aria-selected="true"] { color: var(--neon-2) !important; text-shadow: 0 0 10px rgba(0,212,255,.6); }
.stTabs [data-baseweb="tab-highlight"] { background: var(--neon-2); box-shadow: 0 0 10px var(--neon-2); }

/* bordered containers, forms, expanders = glass panels */
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stForm"], [data-testid="stExpander"] details {
  background: rgba(12,20,36,.55); border: 1px solid var(--line) !important; border-radius: 14px;
  backdrop-filter: blur(6px);
}
[data-testid="stExpander"] summary:hover { color: var(--neon-2); }

/* chat bubbles */
[data-testid="stChatMessage"] { background: rgba(12,20,36,.6); border: 1px solid var(--line); border-radius: 14px; }

/* progress bar */
.stProgress > div > div > div > div { background: linear-gradient(90deg, #1F6BFF, #00D4FF); box-shadow: 0 0 12px #00D4FF; }

/* custom pieces */
.brand { display:flex; align-items:center; gap:12px; margin-bottom: 6px; }
.brand img { height: 52px; filter: drop-shadow(0 0 8px rgba(245,166,35,.35)); }
.brand .name { font-family: 'Orbitron', sans-serif; font-weight: 800; font-size: 1.45rem; letter-spacing: .12em;
               color: #fff; text-shadow: 0 0 10px var(--neon), 0 0 24px rgba(46,139,255,.6); line-height: 1; }
.brand .sub { font-size: .68rem; letter-spacing: .18em; color: var(--muted); text-transform: uppercase; margin-top: 4px; }

.hero { padding: 26px 30px; border-radius: 20px; border: 1px solid var(--line);
        background: linear-gradient(135deg, rgba(31,107,255,.16), rgba(5,7,13,.2) 55%);
        box-shadow: inset 0 0 40px rgba(46,139,255,.08), 0 0 40px rgba(46,139,255,.08); }
.hero-top { display:flex; align-items:center; gap:22px; }
.hero-top img { height: 120px; filter: drop-shadow(0 0 14px rgba(245,166,35,.4)); }
.hero-college { font-size: .8rem; letter-spacing: .22em; color: var(--vnr); text-transform: uppercase; font-weight: 600; }
.hero-title { font-family: 'Orbitron', sans-serif; font-weight: 800; font-size: 3.4rem; letter-spacing: .14em; line-height: 1.05;
              background: linear-gradient(90deg, #FFFFFF, #7FC4FF 45%, #00D4FF);
              -webkit-background-clip: text; background-clip: text; color: transparent;
              filter: drop-shadow(0 0 14px rgba(46,139,255,.55)); }
.hero-tag { font-size: 1.05rem; color: var(--muted); margin-top: 6px; }
.features { display:grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 22px; }
.feature { padding: 14px 16px; border-radius: 14px; background: rgba(12,20,36,.7); border: 1px solid var(--line); }
.feature b { color: #fff; display:block; margin-bottom: 4px; }
.feature span { color: var(--muted); font-size: .9rem; }
.feature .ic { color: var(--neon-2); text-shadow: 0 0 10px var(--neon-2); margin-right: 6px; }

.pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.74rem; font-weight:600; letter-spacing:.04em;
       margin-right:6px; text-transform: uppercase;}
.pill.kind-syllabus {background:rgba(245,166,35,.14); color:#FFC56B; border:1px solid rgba(245,166,35,.35);}
.pill.kind-notes {background:rgba(0,212,255,.12); color:#6FE6FF; border:1px solid rgba(0,212,255,.35);}
.pill.kind-textbook {background:rgba(46,139,255,.14); color:#8CC0FF; border:1px solid rgba(46,139,255,.4);}
.pill.kind-question.paper, .pill.kind-other {background:rgba(160,120,255,.14); color:#C7AEFF; border:1px solid rgba(160,120,255,.35);}

.subject-card { border:1px solid var(--line); border-radius:16px; padding:18px 20px; margin-bottom:14px;
                background: linear-gradient(135deg, rgba(31,107,255,.12), rgba(12,20,36,.6));
                transition: all .2s ease; }
.subject-card:hover { border-color: var(--neon); box-shadow: var(--glow); transform: translateY(-2px); }
.subject-card h4 { margin:0 0 6px 0; color:#fff; }
.subject-card .count { font-family:'Orbitron',sans-serif; color: var(--neon-2); text-shadow: 0 0 8px var(--neon-2); }
.muted {color: var(--muted); font-size:.9rem;}
.notice { border-left:3px solid var(--neon-2); padding:8px 14px; margin:8px 0; background: rgba(0,212,255,.06);
          border-radius: 6px; box-shadow: -4px 0 14px -6px var(--neon-2); }
</style>
""", unsafe_allow_html=True)


def brand_block():
    return (f"<div class='brand'><img src='{EMBLEM_SRC}'/>"
            f"<div><div class='name'>VIGNAN</div><div class='sub'>VNRVJIET · Learning</div></div></div>")

ss = st.session_state
ss.setdefault("user", None)
ss.setdefault("reader", None)        # (resource_id, page) currently open in the reader


# ======================================================================= helpers
def open_reader(resource_id, page):
    ss.reader = (resource_id, page)


def close_reader():
    ss.reader = None


@st.cache_data(show_spinner=False)
def cached_units(subject_id, signature):
    return syllabus.units_for_subject(subject_id)


@st.cache_data(show_spinner="Mapping syllabus topics to pages…")
def cached_study_map(subject_id, signature):
    return syllabus.study_map(subject_id)


@st.cache_data(show_spinner=False, max_entries=40)
def cached_page_png(path, page):
    return ingest.render_page_png(path, page)


def kind_pill(kind):
    return f'<span class="pill kind-{kind}">{kind}</span>'


def reader_panel():
    """Shows one PDF page. Opened by clicking any citation or 'Open' button."""
    if not ss.reader:
        return
    rid, page = ss.reader
    res = db.get_resource(rid)
    if not res or not os.path.exists(res["path"]):
        close_reader()
        return
    total = max(res["pages"], 1)
    page = max(1, min(page, total))
    with st.container(border=True):
        top = st.columns([6, 1])
        top[0].markdown(f"**📖 {res['title']}**  \n<span class='muted'>Page {page} of {total}</span>",
                        unsafe_allow_html=True)
        top[1].button("✕", key="reader_close", on_click=close_reader, help="Close reader")
        nav = st.columns(3)
        nav[0].button("◀ Prev", key="reader_prev", disabled=page <= 1,
                      on_click=open_reader, args=(rid, page - 1), width="stretch")
        nav[1].button("Next ▶", key="reader_next", disabled=page >= total,
                      on_click=open_reader, args=(rid, page + 1), width="stretch")
        with open(res["path"], "rb") as f:
            nav[2].download_button("⬇ PDF", f.read(), file_name=res["filename"],
                                   mime="application/pdf", key="reader_dl", width="stretch")
        st.image(cached_page_png(res["path"], page), width="stretch")


def source_buttons(hits, key_prefix):
    for n, h in enumerate(hits, 1):
        label = f"[{n}] {h['resource_title']} · page {h['page']}"
        if len({x['subject_id'] for x in hits}) > 1:
            label += f"  ({h['subject_name']})"
        st.button(label, key=f"{key_prefix}_src_{n}_{h['id']}", on_click=open_reader,
                  args=(h["resource_id"], h["page"]), help=h["snippet"])


# ======================================================================= ask (AI search)
def ask_panel(subject_ids, key, resources=None, units=None):
    history_key = f"chat_{key}"
    ss.setdefault(history_key, [])

    book_filter, unit = None, None
    if resources or units:
        f1, f2 = st.columns(2)
        if resources:
            books = {r["title"]: r["id"] for r in resources if r["kind"] != "syllabus"}
            chosen = f1.multiselect("Search only in", list(books), placeholder="All uploaded material",
                                    key=f"books_{key}")
            book_filter = [books[c] for c in chosen] or None
        if units:
            names = ["Any unit"] + [f"{u['unit']} · {u['title']}" for u in units]
            pick = f2.selectbox("Unit", names, key=f"unit_{key}")
            if pick != "Any unit":
                unit = units[names.index(pick) - 1]

    for i, turn in enumerate(ss[history_key]):
        with st.chat_message("user"):
            st.write(turn["q"])
        with st.chat_message("assistant", avatar="📚"):
            st.markdown(turn["a"])
            if turn["hits"]:
                st.caption(f"Sources · answered by {turn['provider']}")
                source_buttons(turn["hits"], f"{key}_{i}")

    question = st.chat_input("Ask anything from your syllabus — e.g. “state Thevenin's theorem”",
                             key=f"input_{key}")
    if question:
        query = f"{question} {unit['title']}" if unit else question
        with st.spinner("Searching your faculty's material…"):
            hits = search.search(subject_ids, query, k=5, resource_ids=book_filter)
            text, provider = llm.answer(question, hits)
        ss[history_key].append({"q": question, "a": text, "hits": hits, "provider": provider})
        st.rerun()

    if ss[history_key]:
        st.button("Clear chat", key=f"clear_{key}", on_click=lambda: ss.__setitem__(history_key, []))


# ======================================================================= study map
def study_map_panel(subject, for_faculty=False):
    sig = db.chunk_signature([subject["id"]])
    units = cached_study_map(subject["id"], sig)
    if not units:
        st.info("No syllabus uploaded yet. " + ("Upload one in the **Upload** tab (choose type “syllabus”)."
                if for_faculty else "Your faculty hasn't added the syllabus for this subject yet."))
        return
    total = sum(len(u["topics"]) for u in units)
    covered = sum(u["covered"] for u in units)
    st.markdown(f"**{covered} of {total} syllabus topics** are covered by the uploaded material.")
    st.progress(covered / total if total else 0)
    if for_faculty and covered < total:
        st.warning("Topics marked ⚠️ have no matching material yet — upload a book or notes that cover them.")
    for ui, u in enumerate(units):
        with st.expander(f"{u['unit']} — {u['title']}   ({u['covered']}/{len(u['topics'])} topics)",
                         expanded=(ui == 0)):
            for ti, row in enumerate(u["rows"]):
                cols = st.columns([2, 3])
                cols[0].markdown(("✅ " if row["hits"] else "⚠️ ") + f"**{row['topic']}**")
                with cols[1]:
                    if not row["hits"]:
                        st.caption("Not found in uploaded material")
                    for hi, h in enumerate(row["hits"]):
                        st.button(f"📖 {h['resource_title']} · p.{h['page']}",
                                  key=f"map_{subject['id']}_{ui}_{ti}_{hi}",
                                  on_click=open_reader, args=(h["resource_id"], h["page"]),
                                  help=h["snippet"])


# ======================================================================= library
def library_panel(subject, can_delete=False):
    resources = db.list_resources(subject["id"])
    if not resources:
        st.info("Nothing uploaded yet.")
        return
    for r in resources:
        with st.container(border=True):
            c = st.columns([5, 1, 1] if can_delete else [6, 1])
            c[0].markdown(f"{kind_pill(r['kind'])} **{r['title']}**  \n"
                          f"<span class='muted'>{r['pages']} pages · uploaded {r['uploaded_at']}</span>",
                          unsafe_allow_html=True)
            if r["pages"] and r["text_pages"] / r["pages"] < 0.3:
                c[0].caption("⚠️ Looks like a scanned PDF — text can't be searched. Upload a text-based copy.")
            c[1].button("Open", key=f"open_{r['id']}", on_click=open_reader, args=(r["id"], 1),
                        width="stretch")
            if can_delete:
                if c[2].button("Delete", key=f"del_{r['id']}", width="stretch"):
                    db.delete_resource(r["id"])
                    if ss.reader and ss.reader[0] == r["id"]:
                        close_reader()
                    st.rerun()


def notices_panel(items, can_delete=False):
    if not items:
        st.caption("No notices yet.")
    for a in items:
        sub = f"{a['subject_name']} · " if "subject_name" in a else ""
        cols = st.columns([12, 1]) if can_delete else [st.container()]
        cols[0].markdown(f"<div class='notice'><b>{sub}{a['author'] or ''}</b> "
                         f"<span class='muted'>· {a['created_at']}</span><br>{a['message']}</div>",
                         unsafe_allow_html=True)
        if can_delete and cols[1].button("🗑", key=f"delnotice_{a['id']}"):
            db.delete_announcement(a["id"])
            st.rerun()


def with_reader(body):
    """Lay out the page with the PDF reader on the right when it's open."""
    if ss.reader:
        left, right = st.columns([3, 2], gap="large")
        with left:
            body()
        with right:
            reader_panel()
    else:
        body()


# ======================================================================= sidebar
def sidebar(user, extra=None):
    with st.sidebar:
        st.markdown(brand_block(), unsafe_allow_html=True)
        st.divider()
        st.markdown(f"**{user['full_name']}**  \n<span class='muted'>{user['role'].title()}</span>",
                    unsafe_allow_html=True)
        choice = extra() if extra else None
        st.divider()
        st.caption(f"🤖 AI answers: {llm.provider_name() or 'offline mode (no API key)'}")
        st.caption(f"🔎 Meaning search: {'on' if search.embeddings_available() else 'off (keyword search)'}")
        if st.button("Log out", width="stretch"):
            for k in list(ss.keys()):
                del ss[k]
            st.rerun()
    return choice


# ======================================================================= student
def student_view(user):
    classroom = db.get_classroom(user["classroom_id"])
    subjects = db.subjects_for_classroom(user["classroom_id"])

    def pick():
        names = ["🏠 Classroom home"] + [s["name"] for s in subjects]
        return st.radio("Your subjects", names, key="student_nav")

    choice = sidebar(user, pick)

    if choice == "🏠 Classroom home":
        def body():
            st.title(classroom["name"])
            st.caption("Everything your faculty shared — in one place, searchable.")
            cols = st.columns(2)
            for i, s in enumerate(subjects):
                cols[i % 2].markdown(
                    f"<div class='subject-card'><h4>{s['name']}</h4>"
                    f"<span class='muted'>{s['code'] or ''} · {s['faculty_name'] or 'No faculty'}</span><br>"
                    f"<span class='count'>{s['resource_count']}</span> "
                    f"<span class='muted'>resources</span></div>", unsafe_allow_html=True)
            st.subheader("📢 Latest notices")
            notices_panel(db.announcements_for_classroom(classroom["id"], limit=5))
            st.subheader("🔎 Search across all subjects")
            ask_panel([s["id"] for s in subjects], key=f"class_{classroom['id']}")
        with_reader(body)
        return

    subject = next(s for s in subjects if s["name"] == choice)

    def body():
        st.title(subject["name"])
        st.caption(f"{subject['code'] or ''} · {subject['faculty_name'] or ''} · {classroom['name']}")
        sig = db.chunk_signature([subject["id"]])
        units = cached_units(subject["id"], sig)
        resources = db.list_resources(subject["id"])
        t1, t2, t3, t4 = st.tabs(["💬 Ask", "🗺️ Study Map", "📂 Library", "📢 Notices"])
        with t1:
            ask_panel([subject["id"]], key=f"subj_{subject['id']}", resources=resources, units=units)
        with t2:
            st.caption("Every syllabus topic, and exactly which book and page to read for it.")
            study_map_panel(subject)
        with t3:
            library_panel(subject)
        with t4:
            notices_panel(db.announcements_for_subject(subject["id"]))
    with_reader(body)


# ======================================================================= faculty
def faculty_view(user):
    subjects = db.subjects_for_faculty(user["id"])

    def pick():
        if not subjects:
            return None
        labels = [f"{s['name']} — {s['classroom_name']}" for s in subjects]
        return st.radio("Your subjects", labels, key="faculty_nav")

    choice = sidebar(user, pick)
    if not subjects:
        st.title("Welcome!")
        st.info("You haven't been assigned any subjects yet. Ask the admin to assign one to you.")
        return
    subject = subjects[[f"{s['name']} — {s['classroom_name']}" for s in subjects].index(choice)]

    def body():
        st.title(subject["name"])
        st.caption(f"{subject['classroom_name']} · {subject['code'] or ''}")
        t1, t2, t3, t4, t5 = st.tabs(["⬆️ Upload", "📂 Resources", "🗺️ Syllabus coverage",
                                      "📢 Notices", "💬 Test as student"])
        with t1:
            upload_panel(subject, user)
        with t2:
            library_panel(subject, can_delete=True)
        with t3:
            st.caption("Checks every syllabus topic against what you've uploaded, so you can spot gaps.")
            study_map_panel(subject, for_faculty=True)
        with t4:
            with st.form("notice_form", clear_on_submit=True):
                msg = st.text_area("New notice for this class", placeholder="e.g. Mid-1 covers Units I and II")
                if st.form_submit_button("Post notice") and msg.strip():
                    db.post_announcement(subject["id"], user["id"], msg)
                    st.success("Posted.")
            notices_panel(db.announcements_for_subject(subject["id"]), can_delete=True)
        with t5:
            ask_panel([subject["id"]], key=f"fac_{subject['id']}")
    with_reader(body)


def upload_panel(subject, user):
    st.markdown("Upload PDFs once — every student in the class can search them instantly.")
    kind = st.selectbox("Type of material", db.RESOURCE_KINDS, index=1,
                        help="Choose “syllabus” for the syllabus — VIGNAN reads its units to build the Study Map.")
    files = st.file_uploader("PDF files", type=["pdf"], accept_multiple_files=True,
                             key=f"uploader_{subject['id']}_{ss.get('upload_round', 0)}")
    titles = {}
    for f in files or []:
        default = os.path.splitext(f.name)[0].replace("_", " ").replace("-", " ").title()
        titles[f.name] = st.text_input(f"Title for {f.name}", value=default, key=f"title_{f.name}")
    if files and st.button(f"Upload & index {len(files)} file(s)", type="primary"):
        with st.status("Reading and indexing…", expanded=True) as status:
            for f in files:
                try:
                    rep = ingest.add_pdf(subject["id"], titles[f.name] or f.name, kind, f.name,
                                         f.getvalue(), user["id"])
                    msg = f"✅ {f.name}: {rep['pages']} pages, {rep['chunks']} searchable chunks"
                    if rep["looks_scanned"]:
                        msg += " — ⚠️ looks scanned, most pages have no text"
                    st.write(msg)
                except Exception as e:
                    st.write(f"❌ {f.name}: {e}")
            status.update(label="Done", state="complete")
        ss["upload_round"] = ss.get("upload_round", 0) + 1
        st.cache_data.clear()


# ======================================================================= admin
def admin_view(user):
    sidebar(user)
    st.title("Admin")
    t1, t2, t3 = st.tabs(["🏫 Classrooms", "👩‍🏫 Faculty", "📘 Subjects"])
    classrooms = db.list_classrooms()
    with t1:
        with st.form("new_class", clear_on_submit=True):
            c = st.columns(3)
            branch = c[0].text_input("Branch", placeholder="EIE")
            year = c[1].selectbox("Year", [1, 2, 3, 4], index=1)
            section = c[2].text_input("Section", placeholder="A")
            if st.form_submit_button("Create classroom") and branch and section:
                try:
                    db.create_classroom(branch, year, section)
                    st.rerun()
                except Exception:
                    st.error("That classroom already exists.")
        for c in classrooms:
            n = len(db.subjects_for_classroom(c["id"]))
            st.markdown(f"- **{c['name']}** · {n} subjects")
    with t2:
        with st.form("new_fac", clear_on_submit=True):
            name = st.text_input("Full name", placeholder="Dr. A. Kumar")
            uname = st.text_input("Username", placeholder="dr.kumar")
            pw = st.text_input("Temporary password", type="password")
            if st.form_submit_button("Create faculty account") and name and uname and pw:
                if db.username_exists(uname):
                    st.error("Username taken.")
                else:
                    db.create_user(uname, name, pw, "faculty")
                    st.success(f"Created {name}.")
        for f in db.list_faculty():
            st.markdown(f"- **{f['full_name']}** (`{f['username']}`)")
    with t3:
        faculty = db.list_faculty()
        if not classrooms or not faculty:
            st.info("Create a classroom and a faculty account first.")
        else:
            with st.form("new_subj", clear_on_submit=True):
                cls = st.selectbox("Classroom", classrooms, format_func=lambda c: c["name"])
                sname = st.text_input("Subject name", placeholder="Network Analysis")
                code = st.text_input("Subject code", placeholder="22EI3T02")
                fac = st.selectbox("Faculty", faculty, format_func=lambda f: f["full_name"])
                if st.form_submit_button("Create subject") and sname:
                    db.create_subject(cls["id"], sname, code, fac["id"])
                    st.success(f"Added {sname} to {cls['name']}.")
            for c in classrooms:
                subs = db.subjects_for_classroom(c["id"])
                if subs:
                    st.markdown(f"**{c['name']}**")
                    for s in subs:
                        st.markdown(f"- {s['name']} · {s['faculty_name']} · {s['resource_count']} resources")


# ======================================================================= login
def login_view():
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown(f"""
<div class="hero">
  <div class="hero-top">
    <img src="{EMBLEM_SRC}"/>
    <div>
      <div class="hero-college">VNRVJIET · Vignana Jyothi</div>
      <div class="hero-title">VIGNAN</div>
      <div class="hero-tag">Your classroom's books, notes and syllabus — in one place, not buried in WhatsApp groups.</div>
    </div>
  </div>
  <div class="features">
    <div class="feature"><b><span class="ic">◆</span>One classroom per section</b><span>Faculty upload the syllabus, books and notes once.</span></div>
    <div class="feature"><b><span class="ic">◆</span>Ask in plain English</b><span>AI answers only from your faculty's material.</span></div>
    <div class="feature"><b><span class="ic">◆</span>Exact page, every time</b><span>Every answer cites the book and page — click to open.</span></div>
    <div class="feature"><b><span class="ic">◆</span>Study Map</b><span>Every syllabus topic mapped to where it's taught.</span></div>
  </div>
</div>""", unsafe_allow_html=True)
    with right:
        tab_login, tab_signup = st.tabs(["Log in", "Student sign up"])
        with tab_login:
            with st.form("login"):
                u = st.text_input("Username / roll number")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Log in", type="primary", width="stretch"):
                    user = db.login(u, p)
                    if user:
                        ss.user = user
                        st.rerun()
                    st.error("Wrong username or password.")
            with st.expander("Demo logins"):
                st.markdown("Student `student / student123`  \nFaculty `dr.rao / faculty123`  \n"
                            "Admin `admin / admin123`")
        with tab_signup:
            classrooms = db.list_classrooms()
            if not classrooms:
                st.info("No classrooms yet — the admin needs to create one.")
            else:
                with st.form("signup"):
                    name = st.text_input("Full name")
                    roll = st.text_input("Roll number (your username)")
                    cls = st.selectbox("Your classroom", classrooms, format_func=lambda c: c["name"])
                    pw = st.text_input("Choose a password", type="password")
                    if st.form_submit_button("Create account", width="stretch"):
                        if not (name and roll and pw):
                            st.error("Fill in all fields.")
                        elif len(pw) < 6:
                            st.error("Password must be at least 6 characters.")
                        elif db.username_exists(roll):
                            st.error("That roll number is already registered.")
                        else:
                            db.create_user(roll, name, pw, "student", cls["id"])
                            ss.user = db.login(roll, pw)
                            st.rerun()


# ======================================================================= router
user = ss.user
if not user:
    login_view()
elif user["role"] == "student":
    student_view(user)
elif user["role"] == "faculty":
    faculty_view(user)
else:
    admin_view(user)
