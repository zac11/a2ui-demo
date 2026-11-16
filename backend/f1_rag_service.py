"""F1 RAG data service reading directly from F1_RAG_new/docs-db-2/chroma.sqlite3 and F1_RAG_new/docs."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_F1_RAG_DIR = Path(__file__).resolve().parent.parent.parent / "F1_RAG_new"


def get_f1_rag_dir() -> Path:
    env_dir = os.environ.get("F1_RAG_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return DEFAULT_F1_RAG_DIR


def _connect_db() -> sqlite3.Connection:
    db_path = get_f1_rag_dir() / "docs-db-2" / "chroma.sqlite3"
    if not db_path.exists():
        raise FileNotFoundError(f"ChromaDB sqlite not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _categorize_title(title: str) -> str:
    t = title.lower()
    if "world championship" in t or "season" in t or re.match(r"^\d{4}\s+formula one", t):
        return "Seasons & Championships"
    if "grand prix" in t or "circuit" in t or "ring" in t or "autodromo" in t or "silverstone" in t or "monza" in t or "spa-" in t:
        return "Circuits & Grands Prix"
    if "engine" in t or "v8" in t or "v10" in t or "v12" in t or "turbo" in t or "power unit" in t:
        return "Engines & Power Units"
    if "controversy" in t or "accident" in t or "crash" in t or "cheating" in t or "spygate" in t or "crashgate" in t:
        return "Controversies & Incidents"
    if any(k in t for k in ["racing", "team", "scuderia", "williams", "mclaren", "ferrari", "mercedes", "red bull", "lotus", "brabham", "tyrrell", "renault", "benetton", "jordan", "sauber", "haas", "alpine", "aston martin"]):
        if re.search(r"\b[a-z]+\d+\b", t) or re.search(r"\brb\d|\bf\d|\bmp4|\bw\d", t):
            return "Cars & Chassis"
        return "Constructors & Teams"
    if re.search(r"\b(rb\d|fw\d|mp4|sf\d|w\d{2}|f20\d{2}|bt\d|cg\d|a\d{2}|fa\d{2}|t\d{2})\b", t):
        return "Cars & Chassis"
    return "Drivers, Rules & Lore"


def _clean_wikipedia_boilerplate(text: str) -> str:
    """Strip common Wikipedia navigation/chrome boilerplate from scraped HTML text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    skip_phrases = {
        "Jump to content",
        "Main menu",
        "move to sidebar",
        "hide",
        "Navigation",
        "Main pageContentsCurrent eventsRandom articleAbout WikipediaContact usDonate",
        "Contribute",
        "HelpLearn to editCommunity portalRecent changesUpload file",
        "Languages",
        "Language links are at the top of the page.",
        "Search",
        "Create account",
        "Log in",
        "Personal tools",
        "Create account Log in",
        "Pages for logged out editors learn more",
        "ContributionsTalk",
        "Contents",
        "(Top)",
        "Toggle the table of contents",
        "Add languages",
        "Add links",
        "ArticleTalk",
        "English",
        "ReadEditView history",
        "Tools",
        "Actions",
        "General",
        "What links hereRelated changesUpload fileSpecial pagesPermanent linkPage informationCite this pageGet shortened URLWikidata item",
        "Print/export",
        "Download as PDFPrintable version",
        "From Wikipedia, the free encyclopedia",
    }
    cleaned = [ln for ln in lines if ln not in skip_phrases]
    return " ".join(cleaned).strip()


def get_corpus_stats() -> dict[str, Any]:
    """Return real statistics from chroma.sqlite3 and docs/."""
    rag_dir = get_f1_rag_dir()
    docs_dir = rag_dir / "docs"
    html_files = sorted(f.name for f in docs_dir.glob("*.html")) if docs_dir.exists() else []

    conn = _connect_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM embeddings")
        total_chunks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT string_value) FROM embedding_metadata WHERE key = 'source'")
        total_indexed_sources = cur.fetchone()[0]

        cur.execute(
            """
            SELECT string_value AS source, COUNT(*) AS chunk_count
            FROM embedding_metadata
            WHERE key = 'source'
            GROUP BY string_value
            ORDER BY chunk_count DESC
            LIMIT 12
            """
        )
        top_sources = [
            {
                "source": row["source"],
                "title": Path(row["source"]).stem,
                "chunks": row["chunk_count"],
                "category": _categorize_title(Path(row["source"]).stem),
            }
            for row in cur.fetchall()
        ]

        cur.execute("SELECT DISTINCT string_value FROM embedding_metadata WHERE key = 'source'")
        all_sources = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

    category_counts = Counter(_categorize_title(Path(s).stem) for s in all_sources)
    categories = [
        {"name": name, "count": count}
        for name, count in category_counts.most_common()
    ]

    return {
        "totalHtmlDocs": len(html_files),
        "totalIndexedSources": total_indexed_sources,
        "totalChunks": total_chunks,
        "avgChunksPerDoc": round(total_chunks / max(total_indexed_sources, 1), 1),
        "collectionName": "custom-f1-data",
        "embeddingModel": "text-embedding-ada-002",
        "categories": categories,
        "topSources": top_sources,
        "sampleQuestions": [
            "Who built the Nurburgring?",
            "Which team has the most wins in F1?",
            "When did Niki Lauda famously have his accident?",
            "What was the 1984 Tyrrell Racing controversy?",
            "Tell me about the Mercedes-Benz FO engine",
            "What happened in the 2024 Formula One World Championship?",
        ],
    }


def list_documents(category: str | None = None, search: str | None = None, limit: int = 60) -> list[dict[str, Any]]:
    """List indexed F1 documents with chunk counts and categories."""
    conn = _connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT string_value AS source, COUNT(*) AS chunk_count
            FROM embedding_metadata
            WHERE key = 'source'
            GROUP BY string_value
            ORDER BY source ASC
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    q = (search or "").strip().lower()
    for row in rows:
        src = row["source"]
        title = Path(src).stem
        cat = _categorize_title(title)
        if category and category != "All" and cat != category:
            continue
        if q and q not in title.lower():
            continue
        results.append(
            {
                "source": src,
                "title": title,
                "category": cat,
                "chunks": row["chunk_count"],
            }
        )
        if len(results) >= limit:
            break
    return results


def get_document_chunks(source: str, limit: int = 15) -> list[dict[str, Any]]:
    """Fetch stored chunks for a given source document."""
    conn = _connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT e.id AS embedding_id,
                   doc.string_value AS content,
                   title.string_value AS title
            FROM embedding_metadata src
            JOIN embeddings e ON e.id = src.id
            LEFT JOIN embedding_metadata doc ON doc.id = src.id AND doc.key = 'chroma:document'
            LEFT JOIN embedding_metadata title ON title.id = src.id AND title.key = 'title'
            WHERE src.key = 'source' AND src.string_value = ?
            LIMIT ?
            """,
            (source, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    chunks = []
    for idx, row in enumerate(rows):
        raw = row["content"] or ""
        cleaned = _clean_wikipedia_boilerplate(raw)
        if not cleaned:
            cleaned = raw.strip()
        chunks.append(
            {
                "index": idx + 1,
                "embeddingId": row["embedding_id"],
                "title": row["title"] or Path(source).stem,
                "content": cleaned[:900],
            }
        )
    return chunks


def _fts_sanitize(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", query)
    stop = {"who", "what", "when", "where", "why", "how", "is", "are", "was", "were", "the", "a", "an", "in", "on", "of", "to", "did", "have", "has", "most", "tell", "me", "about", "famous", "famously"}
    filtered = [t for t in tokens if t.lower() not in stop and len(t) > 1]
    if not filtered:
        filtered = tokens
    if not filtered:
        return "Formula"
    return " OR ".join(f'"{t}"' for t in filtered[:8])


def retrieve_chunks(query: str, k: int = 8) -> list[dict[str, Any]]:
    """Retrieve top-k chunks using SQLite FTS5 BM25 on ChromaDB's fulltext index."""
    fts_query = _fts_sanitize(query)
    conn = _connect_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT fts.rowid AS emb_id,
                   bm25(embedding_fulltext_search) AS rank_score,
                   doc.string_value AS raw_text,
                   src.string_value AS source,
                   ttl.string_value AS title
            FROM embedding_fulltext_search fts
            LEFT JOIN embedding_metadata doc ON doc.id = fts.rowid AND doc.key = 'chroma:document'
            LEFT JOIN embedding_metadata src ON src.id = fts.rowid AND src.key = 'source'
            LEFT JOIN embedding_metadata ttl ON ttl.id = fts.rowid AND ttl.key = 'title'
            WHERE embedding_fulltext_search MATCH ?
            ORDER BY rank_score ASC
            LIMIT ?
            """,
            (fts_query, k * 3),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    seen_snippets: set[str] = set()
    results: list[dict[str, Any]] = []
    for row in rows:
        cleaned = _clean_wikipedia_boilerplate(row["raw_text"] or "")
        if len(cleaned) < 60 or cleaned.startswith("^ ") or cleaned.count("^ ") >= 3:
            continue
        sig = cleaned[:120]
        if sig in seen_snippets:
            continue
        seen_snippets.add(sig)
        source = row["source"] or "Unknown"
        title = (row["title"] or Path(source).stem).replace(" - Wikipedia", "")
        results.append(
            {
                "embeddingId": row["emb_id"],
                "source": source,
                "title": title,
                "category": _categorize_title(title),
                "score": round(abs(float(row["rank_score"])), 3),
                "content": cleaned[:700],
            }
        )
        if len(results) >= k:
            break
    return results


def _call_openai_if_available(question: str, chunks: list[dict[str, Any]], api_key: str | None) -> str | None:
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    context = "\n\n".join(
        f"Source: {c['source']}\nContent: {c['content']}" for c in chunks[:6]
    )
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0.0,
        "messages": [
            {
                "role": "system",
                "content": "You are an F1 RAG assistant. Answer concisely using ONLY the provided context, and cite the source filenames.",
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{context}",
            },
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, IndexError, TimeoutError):
        return None


def answer_rag_query(question: str, k: int = 8, openai_api_key: str | None = None) -> dict[str, Any]:
    """Run retrieval + optional LLM synthesis and return structured RAG result."""
    chunks = retrieve_chunks(question, k=k)
    llm_answer = _call_openai_if_available(question, chunks, openai_api_key)

    if llm_answer:
        mode = "OpenAI LLM + Chroma FTS5"
        answer = llm_answer
    elif chunks:
        mode = "Extractive ChromaDB FTS5 (BM25)"
        top_titles = list(dict.fromkeys(c["title"] for c in chunks[:4]))
        lead = chunks[0]["content"]
        sentences = re.split(r"(?<=[.!?])\s+", lead)
        summary = " ".join(sentences[:3]).strip()
        answer = (
            f"Based on {len(chunks)} retrieved passages from {', '.join(top_titles)}: "
            f"{summary}"
        )
    else:
        mode = "Extractive ChromaDB FTS5 (BM25)"
        answer = "No matching passages were found in the F1_RAG_new ChromaDB index for that query."

    unique_sources = []
    seen = set()
    for c in chunks:
        if c["source"] not in seen:
            seen.add(c["source"])
            unique_sources.append({"source": c["source"], "title": c["title"], "category": c["category"]})

    return {
        "question": question,
        "mode": mode,
        "answer": answer,
        "chunks": chunks,
        "sources": unique_sources,
    }
