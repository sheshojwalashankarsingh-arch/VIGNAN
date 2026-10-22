# 📚 VIGNAN — VNR's Learning Platform

**Problem.** Study material reaches students through WhatsApp groups. PDFs and books get buried under
hundreds of messages, nobody knows which file has which topic, and finding a topic inside a 600-page book
takes longer than studying it. Students give up before they start.

**Solution.** VIGNAN (from VNR **Vignana** Jyothi — *vignan* means knowledge) gives every class section its own digital classroom. Faculty upload the syllabus,
reference books and notes once. Students ask questions in plain English, and an AI answers **only from
their faculty's material**, citing the exact book and page — one click opens that page.

## Features

| For students | For faculty | For admin |
|---|---|---|
| Classroom home with all subjects + notices | Upload PDFs (bulk), auto-indexed | Create classrooms (branch / year / section) |
| **Ask** — AI answers with `[1]` `[2]` citations | **Syllabus coverage** — see which topics have no material yet | Create faculty accounts |
| Click a citation → reader opens at that page | Post / delete notices | Assign subjects to faculty |
| **Study Map** — every syllabus topic → book + page | Test the AI exactly as students see it | |
| Filter by book or by unit | Warning when a PDF is scanned (no text) | |
| Search across all subjects at once | | |

## How it works (RAG — Retrieval-Augmented Generation)

```
 Faculty uploads PDF
        │
        ▼
 ingest.py   read each page (PyMuPDF) ──► cut into ~120-word chunks, keep page number ──► SQLite
                                                                                          │
 Student asks "state Thevenin's theorem"                                                  │
        │                                                                                 ▼
        ▼                                                                   search.py  hybrid search
 search.py  ── BM25 keyword score  +  (optional) embedding "meaning" score ──► top 5 chunks
        │
        ▼
 llm.py     sends ONLY those chunks + the question to the AI model
            "answer only from these sources, cite [n]"  ──►  answer + citations
        │
        ▼
 app.py     shows answer · [1] Notes p.5 · [2] Problem book p.1   (click = open that page)

 syllabus.py  reads UNIT I…V from the syllabus PDF, searches every topic ──► Study Map
```

Why this design: the AI never "remembers" textbooks — it only sees what search found, so answers stay
faithful to the faculty's material, and every claim can be checked on the cited page.

## Run it (Windows / Mac / Linux)

```bash
cd vignan
python -m venv venv
venv\Scripts\activate            # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python seed_demo.py              # creates a demo college with sample PDFs
streamlit run app.py             # opens http://localhost:8501
```

Demo logins — student `student / student123` · faculty `dr.rao / faculty123` · admin `admin / admin123`

### Turn on AI-written answers (free)
Without a key, VIGNAN runs in **offline mode**: it shows the best matching passages with citations.
For written answers, copy `.env.example` to `.env` and add **one** key:
- **Gemini** — free key at aistudio.google.com/apikey
- **Groq** — free key at console.groq.com/keys
- **Ollama** — no internet needed; install Ollama, run `ollama pull llama3.2`, set `OLLAMA_MODEL=llama3.2`

AI providers retire model names often. If answers stop working, set `GEMINI_MODEL` / `GROQ_MODEL` in
`.env` to a current model from the provider's model list.

### Turn on "meaning" search (optional)
`pip install sentence-transformers` and restart. Now "voltage around a closed path" also finds the
Kirchhoff's voltage law page even when the words differ. The sidebar shows whether it's on.

### Tests
```bash
python -m pytest -q
```

## Project structure

| File | What it does | Suggested owner |
|---|---|---|
| `app.py` | All screens: login, student, faculty, admin, PDF reader | UI person |
| `db.py` | SQLite tables and every query | Database person |
| `ingest.py` | PDF → page text → chunks; page rendering for the reader | Data person |
| `search.py` | BM25 + embedding hybrid search | AI person |
| `llm.py` | Prompt, Gemini / Groq / Ollama calls, offline fallback | AI person |
| `syllabus.py` | Parses units/topics, builds the Study Map | Data person |
| `seed_demo.py` | Demo college + sample PDFs | Anyone |
| `tests/` | Automated checks | Everyone |

## 5-minute demo script (for the viva)

1. **Problem (30 s):** show a screenshot of a flooded WhatsApp group.
2. **Faculty (1 min):** log in as `dr.rao` → Upload a real PDF → show it indexed in seconds →
   *Syllabus coverage* shows which topics are still missing material.
3. **Student (2 min):** log in as `student` → Network Analysis → *Ask* "what is the condition for maximum
   power transfer" → click citation → the exact page opens beside the answer.
4. **Study Map (1 min):** expand Unit II → every topic links to its page.
5. **Tech (30 s):** explain the RAG diagram above and why answers can't be made up.

## Limitations & next steps
- **Scanned PDFs** have no text layer; VIGNAN warns about them. Next step: OCR with Tesseract.
- **Copyright:** meant as an internal college platform — only logged-in students of that class can see
  material, the same way a college library works. Don't host it publicly with copyrighted books.
- Ideas: host on a college server, a WhatsApp bot that answers from the same classroom, previous-year
  question papers mapped to topics, "important questions per unit", Telugu/Hindi answers.
