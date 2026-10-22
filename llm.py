"""
llm.py — writes the final answer from the chunks that search.py found.

This is the "G" in RAG (Retrieval-Augmented Generation):
  retrieved chunks  +  student's question  ->  AI model  ->  answer with [1] [2] citations

The model is told to use ONLY the faculty's material, so it cannot invent
things that are not in the course books.

Pick a provider with environment variables (first one found is used):
  GEMINI_API_KEY   -> Google Gemini   (free tier: https://aistudio.google.com)
  GROQ_API_KEY     -> Groq            (free tier: https://console.groq.com)
  OLLAMA_MODEL     -> Ollama, runs fully on your own laptop (e.g. "llama3.2")
If none is set, VIGNAN still works: it shows the best matching passages
from the books instead of a written answer ("offline mode").
"""

import os

import requests

from search import best_snippet

SYSTEM_PROMPT = """You are VIGNAN, VNR VJIET's learning assistant, a study assistant for engineering students.
Answer the student's question using ONLY the numbered course sources below,
which were uploaded by their faculty.

Rules:
- Every fact must come from the sources. Put the source number in square
  brackets after it, like [1] or [2][3].
- If the sources do not contain the answer, reply exactly:
  "I couldn't find this in your course material." and suggest which topic to ask about instead.
- Write for exam preparation: a short direct answer first, then key points
  as bullets, then any formula on its own line. Keep it under 250 words.
- Never invent page numbers, formulas or facts that are not in the sources."""


def provider_name():
    if os.environ.get("GEMINI_API_KEY"):
        return f"Gemini ({os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash-lite')})"
    if os.environ.get("GROQ_API_KEY"):
        return f"Groq ({os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')})"
    if os.environ.get("OLLAMA_MODEL"):
        return f"Ollama ({os.environ['OLLAMA_MODEL']}, local)"
    return None


def build_context(hits):
    blocks = []
    for n, h in enumerate(hits, 1):
        blocks.append(f"[{n}] {h['resource_title']} — page {h['page']}\n{h['text']}")
    return "\n\n".join(blocks)


def _gemini(question, context):
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": f"SOURCES:\n{context}\n\nQUESTION: {question}"}]}],
        "generationConfig": {"temperature": 0.2},
    }
    r = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=body, timeout=60)
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def _openai_style(url, key, model, question, context):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"SOURCES:\n{context}\n\nQUESTION: {question}"},
        ],
    }
    r = requests.post(url, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _groq(question, context):
    return _openai_style("https://api.groq.com/openai/v1/chat/completions",
                         os.environ["GROQ_API_KEY"],
                         os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
                         question, context)


def _ollama(question, context):
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    return _openai_style(f"{host}/v1/chat/completions", None,
                         os.environ["OLLAMA_MODEL"], question, context)


def offline_answer(question, hits):
    """No AI model configured: stitch together the best sentences, with citations."""
    if not hits:
        return "I couldn't find this in your course material."
    lines = ["**Here's what your course material says:**", ""]
    top = hits[0].get("score", 1.0)
    for n, h in enumerate(hits[:4], 1):
        if n > 1 and h.get("score", 1.0) < 0.6 * top:   # skip weakly related passages
            continue
        lines.append(f"- {best_snippet(h['text'], question, 400)} [{n}]")
    lines += ["", "_Offline mode — add a free Gemini or Groq key to get a written answer._"]
    return "\n".join(lines)


def answer(question, hits):
    """Returns (answer_text, provider_label)."""
    if not hits:
        return ("I couldn't find this in your course material. Try different words, "
                "or check that your faculty has uploaded the book for this topic.", "search")
    context = build_context(hits)
    try:
        if os.environ.get("GEMINI_API_KEY"):
            return _gemini(question, context), provider_name()
        if os.environ.get("GROQ_API_KEY"):
            return _groq(question, context), provider_name()
        if os.environ.get("OLLAMA_MODEL"):
            return _ollama(question, context), provider_name()
    except Exception as e:  # network down, bad key, quota — never crash the student's page
        text = offline_answer(question, hits)
        return text + f"\n\n_(AI model unavailable: {type(e).__name__}. Showing passages instead.)_", "offline"
    return offline_answer(question, hits), "offline"
