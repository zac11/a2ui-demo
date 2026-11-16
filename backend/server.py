"""HTTP server exposing F1 RAG data and A2UI v1.0 wire protocol endpoints."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from a2ui_generator import (
    build_doc_inspector_messages,
    build_overview_messages,
    build_rag_answer_messages,
)
from f1_rag_service import (
    answer_rag_query,
    get_corpus_stats,
    get_document_chunks,
    list_documents,
)


class F1A2uiHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-OpenAI-Key")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        try:
            if path == "/api/health":
                self._send_json(200, {"status": "ok", "protocol": "a2ui-v1.0"})
                return

            if path == "/api/a2ui/overview":
                stats = get_corpus_stats()
                messages = build_overview_messages(stats)
                self._send_json(200, {"messages": messages, "stats": stats})
                return

            if path == "/api/docs":
                category = qs.get("category", [None])[0]
                search = qs.get("search", [None])[0]
                limit = int(qs.get("limit", ["80"])[0])
                docs = list_documents(category=category, search=search, limit=limit)
                self._send_json(200, {"documents": docs})
                return

            if path == "/api/a2ui/document":
                source = qs.get("source", [""])[0]
                title = qs.get("title", [source])[0]
                if not source:
                    self._send_json(400, {"error": "Missing source parameter"})
                    return
                chunks = get_document_chunks(source, limit=20)
                messages = build_doc_inspector_messages(source, title, chunks)
                self._send_json(200, {"messages": messages, "chunks": chunks})
                return

            self._send_json(404, {"error": f"Unknown endpoint: {path}"})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_json_body()

            if path == "/api/a2ui/query":
                question = str(body.get("question", "")).strip()
                if not question:
                    self._send_json(400, {"error": "Question is required"})
                    return
                k = int(body.get("k", 8))
                api_key = body.get("openaiApiKey") or self.headers.get("X-OpenAI-Key")
                rag_result = answer_rag_query(question, k=k, openai_api_key=api_key)
                messages = build_rag_answer_messages(rag_result)
                self._send_json(200, {"messages": messages, "rag": rag_result})
                return

            if path == "/api/a2ui/action":
                action = body.get("action", body)
                name = action.get("name") or action.get("event", {}).get("name")
                context = action.get("context") or action.get("event", {}).get("context") or {}

                if name == "inspect_document":
                    source = context.get("source", "")
                    title = context.get("title", source)
                    chunks = get_document_chunks(source, limit=20)
                    messages = build_doc_inspector_messages(source, title, chunks)
                    self._send_json(200, {"surfaceId": "f1-doc-inspector", "messages": messages})
                    return

                if name == "ask_question":
                    question = context.get("question", "")
                    rag_result = answer_rag_query(question, k=8)
                    messages = build_rag_answer_messages(rag_result)
                    self._send_json(200, {"surfaceId": "f1-rag-answer", "messages": messages})
                    return

                self._send_json(400, {"error": f"Unsupported A2UI action: {name}"})
                return

            self._send_json(404, {"error": f"Unknown endpoint: {path}"})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": str(exc)})


class ReuseThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main() -> None:
    port = int(os.environ.get("PORT", "8001"))
    server = ReuseThreadingHTTPServer(("127.0.0.1", port), F1A2uiHandler)
    print(f"F1 RAG A2UI server listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
