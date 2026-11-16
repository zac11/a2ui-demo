"""Generates A2UI v1.0 wire protocol messages for the F1 RAG Dashboard."""

from __future__ import annotations

from typing import Any

BASIC_CATALOG_ID = "https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json"
F1_CATALOG_ID = "https://a2ui.org/custom/f1-rag/v1/catalog.json"


def build_overview_messages(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Build A2UI v1.0 messages for the F1 Corpus Telemetry overview surface."""
    surface_id = "f1-overview"

    top_source_ids = []
    top_source_components: list[dict[str, Any]] = []
    for idx, item in enumerate(stats["topSources"][:8]):
        row_id = f"top_src_row_{idx}"
        label_id = f"top_src_lbl_{idx}"
        btn_id = f"top_src_btn_{idx}"
        btn_txt_id = f"top_src_btn_txt_{idx}"
        top_source_ids.append(row_id)
        top_source_components.extend(
            [
                {
                    "id": row_id,
                    "component": "Row",
                    "children": [label_id, btn_id],
                },
                {
                    "id": label_id,
                    "component": "Text",
                    "text": f"**{item['title']}** · `{item['category']}` ({item['chunks']} chunks)",
                },
                {
                    "id": btn_txt_id,
                    "component": "Text",
                    "text": "Inspect Chunks",
                },
                {
                    "id": btn_id,
                    "component": "Button",
                    "child": btn_txt_id,
                    "variant": "borderless",
                    "action": {
                        "event": {
                            "name": "inspect_document",
                            "userMessage": f"Inspect {item['title']}",
                            "context": {
                                "source": item["source"],
                                "title": item["title"],
                            },
                        }
                    },
                },
            ]
        )

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": ["kpi_row", "cat_chart", "top_sources_card"],
        },
        {
            "id": "kpi_row",
            "component": "Row",
            "children": ["kpi_chunks", "kpi_docs", "kpi_avg", "kpi_model"],
        },
        {
            "id": "kpi_chunks",
            "component": "F1StatTile",
            "label": "VECTOR CHUNKS",
            "value": {"@path": "/kpis/totalChunks"},
            "sublabel": "Indexed in ChromaDB",
            "accent": "red",
        },
        {
            "id": "kpi_docs",
            "component": "F1StatTile",
            "label": "F1 ARTICLES",
            "value": {"@path": "/kpis/totalDocs"},
            "sublabel": "Wikipedia HTML sources",
            "accent": "teal",
        },
        {
            "id": "kpi_avg",
            "component": "F1StatTile",
            "label": "AVG CHUNKS / DOC",
            "value": {"@path": "/kpis/avgChunks"},
            "sublabel": "1000 chars · 200 overlap",
            "accent": "amber",
        },
        {
            "id": "kpi_model",
            "component": "F1StatTile",
            "label": "COLLECTION",
            "value": {"@path": "/kpis/collection"},
            "sublabel": {"@path": "/kpis/embeddingModel"},
            "accent": "blue",
        },
        {
            "id": "cat_chart",
            "component": "F1BarChart",
            "title": "Knowledge Base Breakdown by F1 Domain",
            "items": {"@path": "/categories"},
        },
        {
            "id": "top_sources_card",
            "component": "Card",
            "child": "top_sources_col",
        },
        {
            "id": "top_sources_col",
            "component": "Column",
            "children": ["top_sources_hdr", *top_source_ids],
        },
        {
            "id": "top_sources_hdr",
            "component": "Text",
            "text": "### Densest F1 Articles in Vector Store",
        },
        *top_source_components,
    ]

    data_model = {
        "kpis": {
            "totalChunks": f"{stats['totalChunks']:,}",
            "totalDocs": f"{stats['totalHtmlDocs']:,}",
            "avgChunks": str(stats["avgChunksPerDoc"]),
            "collection": stats["collectionName"],
            "embeddingModel": stats["embeddingModel"],
        },
        "categories": stats["categories"],
    }

    return [
        {
            "version": "v1.0",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": BASIC_CATALOG_ID,
                "sendDataModel": False,
                "components": components,
                "dataModel": data_model,
            },
        }
    ]


def build_rag_answer_messages(rag_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Build A2UI v1.0 messages for a dynamic RAG query response surface."""
    surface_id = "f1-rag-answer"
    chunks = rag_result.get("chunks", [])

    chunk_ids: list[str] = []
    chunk_components: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        cid = f"passage_{idx}"
        chunk_ids.append(cid)
        chunk_components.append(
            {
                "id": cid,
                "component": "F1PassageCard",
                    "rank": idx + 1,
                "title": chunk["title"],
                "source": chunk["source"],
                "category": chunk["category"],
                "score": chunk["score"],
                "content": chunk["content"],
                "action": {
                    "event": {
                        "name": "inspect_document",
                        "userMessage": f"Inspect {chunk['title']}",
                        "context": {
                            "source": chunk["source"],
                            "title": chunk["title"],
                        },
                    }
                },
            }
        )

    children = ["answer_card", "sources_hdr", *chunk_ids] if chunk_ids else ["answer_card"]

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": children,
        },
        {
            "id": "answer_card",
            "component": "Card",
            "child": "answer_col",
        },
        {
            "id": "answer_col",
            "component": "Column",
            "children": ["answer_meta", "answer_body"],
        },
        {
            "id": "answer_meta",
            "component": "Text",
            "text": {"@path": "/metaLine"},
            "variant": "caption",
        },
        {
            "id": "answer_body",
            "component": "Text",
            "text": {"@path": "/answer"},
        },
        {
            "id": "sources_hdr",
            "component": "Text",
            "text": f"### Retrieved Evidence ({len(chunks)} chunks)",
        },
        *chunk_components,
    ]

    data_model = {
        "question": rag_result["question"],
        "metaLine": f"MODE: {rag_result['mode']}  ·  SOURCES: {len(rag_result.get('sources', []))} articles  ·  CHUNKS: {len(chunks)}",
        "answer": rag_result["answer"],
    }

    return [
        {
            "version": "v1.0",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": BASIC_CATALOG_ID,
                "sendDataModel": False,
                "components": components,
                "dataModel": data_model,
            },
        }
    ]


def build_doc_inspector_messages(source: str, title: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build A2UI v1.0 messages for inspecting a single F1 document's stored chunks."""
    surface_id = "f1-doc-inspector"
    chunk_ids: list[str] = []
    chunk_components: list[dict[str, Any]] = []

    for idx, ch in enumerate(chunks):
        cid = f"doc_chunk_{idx}"
        chunk_ids.append(cid)
        chunk_components.append(
            {
                "id": cid,
                "component": "F1PassageCard",
                    "rank": ch["index"],
                "title": f"Chunk #{ch['index']} · {title}",
                "source": source,
                "category": f"ID {ch['embeddingId']}",
                "score": 1.0,
                "content": ch["content"],
            }
        )

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": ["doc_hdr_card", *chunk_ids],
        },
        {
            "id": "doc_hdr_card",
            "component": "Card",
            "child": "doc_hdr_col",
        },
        {
            "id": "doc_hdr_col",
            "component": "Column",
            "children": ["doc_title", "doc_sub"],
        },
        {
            "id": "doc_title",
            "component": "Text",
            "text": f"## {title}",
        },
        {
            "id": "doc_sub",
            "component": "Text",
            "text": f"Source: `{source}` · Showing {len(chunks)} stored chunks from ChromaDB",
            "variant": "caption",
        },
        *chunk_components,
    ]

    return [
        {
            "version": "v1.0",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": BASIC_CATALOG_ID,
                "sendDataModel": False,
                "components": components,
                "dataModel": {"source": source, "title": title},
            },
        }
    ]
