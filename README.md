# F1 RAG · A2UI v1.0 Telemetry Dashboard

An interactive generative UI dashboard built with **A2UI v1.0** (`@a2ui/react`, `@a2ui/web_core`, `@a2ui/markdown-it`) for exploring and querying the Formula 1 RAG dataset in `../F1_RAG_new` (979 Wikipedia HTML documents, 29,851 ChromaDB chunks).

## Architecture

- **Backend (`backend/`)**:
  - `f1_rag_service.py`: Reads directly from `../F1_RAG_new/docs-db-2/chroma.sqlite3` (FTS5 BM25 retrieval, corpus analytics, and chunk inspection) with optional OpenAI synthesis.
  - `a2ui_generator.py`: Emits A2UI v1.0 wire protocol messages (`createSurface`, `components`, `dataModel`, `action` events) using both `basicCatalog` (`Column`, `Row`, `Card`, `Text`, `Button`) and the custom `f1Catalog` (`F1StatTile`, `F1BarChart`, `F1PassageCard`).
  - `server.py`: Zero-dependency Python HTTP server on `http://127.0.0.1:8001`.
- **Frontend (`frontend/`)**:
  - React + TypeScript + Vite app using `MessageProcessor` and `A2uiSurface` from `@a2ui/react` and `@a2ui/web_core/v1_0`.
  - Custom F1 telemetry components registered in `src/f1Catalog.tsx`.
  - Includes **Corpus Telemetry**, **RAG Query**, **Knowledge Explorer**, and a live **A2UI Wire JSON** inspector.

## Running Locally

1. **Start the Python A2UI backend**:
   ```bash
   python3 backend/server.py
   ```
   *(Set `F1_RAG_DIR=/path/to/F1_RAG_new` if your `F1_RAG_new` folder is in a different location, and optionally `OPENAI_API_KEY` for GPT synthesis.)*

2. **Start the React + A2UI frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Open `http://localhost:5173` in your browser.
