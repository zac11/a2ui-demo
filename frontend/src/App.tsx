import { type ComponentProps, useCallback, useEffect, useMemo, useState } from 'react';
import { renderMarkdown } from '@a2ui/markdown-it';
import { A2uiSurface, type ReactCatalogComponent } from '@a2ui/react';
import {
  type ActionPayload,
  MessageProcessor,
  type ProcessableMessage,
  basicCatalog,
  injectBasicCatalogStyles,
  setMarkdownRenderer,
} from '@a2ui/web_core/v1_0';
import {
  Activity,
  Code2,
  Database,
  FileText,
  Gauge,
  Search,
  Sparkles,
} from 'lucide-react';
import { f1Catalog } from './f1Catalog';

injectBasicCatalogStyles();
setMarkdownRenderer(renderMarkdown);

type TabId = 'query' | 'overview' | 'explorer';

interface CorpusStats {
  totalHtmlDocs: number;
  totalIndexedSources: number;
  totalChunks: number;
  avgChunksPerDoc: number;
  collectionName: string;
  embeddingModel: string;
  categories: Array<{ name: string; count: number }>;
  sampleQuestions: string[];
}

interface DocEntry {
  source: string;
  title: string;
  category: string;
  chunks: number;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [showWire, setShowWire] = useState(false);
  const [wireLog, setWireLog] = useState<unknown[]>([]);
  const [surfaceTick, setSurfaceTick] = useState(0);

  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [question, setQuestion] = useState('Who built the Nurburgring?');
  const [openaiKey, setOpenaiKey] = useState('');
  const [loadingQuery, setLoadingQuery] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [docs, setDocs] = useState<DocEntry[]>([]);
  const [docCategory, setDocCategory] = useState('All');
  const [docSearch, setDocSearch] = useState('');
  const [selectedSource, setSelectedSource] = useState<string | null>(null);

  const sendActionToAgent = useCallback(
    async (action: ActionPayload, proc: MessageProcessor<ReactCatalogComponent>) => {
      try {
        setErrorMsg(null);
        const res = await fetch('/api/a2ui/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ version: 'v1.0', action }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Action failed');
        if (Array.isArray(data.messages)) {
          proc.processMessages(data.messages as ProcessableMessage[]);
          setWireLog(data.messages);
          setSurfaceTick((t) => t + 1);
        }
        if (data.surfaceId === 'f1-doc-inspector') {
          const ctx = (action as { context?: { source?: string } }).context;
          if (ctx?.source) setSelectedSource(ctx.source);
          setActiveTab('explorer');
        } else if (data.surfaceId === 'f1-rag-answer') {
          setActiveTab('query');
        }
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
      }
    },
    [],
  );

  const processor = useMemo(() => {
    const proc = new MessageProcessor<ReactCatalogComponent>(
      [basicCatalog, f1Catalog],
      (action: ActionPayload) => {
        void sendActionToAgent(action, proc);
      },
    );
    return proc;
  }, [sendActionToAgent]);

  const applyMessages = useCallback(
    (messages: ProcessableMessage[]) => {
      processor.processMessages(messages);
      setWireLog(messages);
      setSurfaceTick((t) => t + 1);
    },
    [processor],
  );

  // Load initial A2UI overview surface
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/a2ui/overview');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to load overview');
        if (cancelled) return;
        setStats(data.stats);
        applyMessages(data.messages);
      } catch (err) {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : String(err));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyMessages]);

  // Load document list when explorer filter changes
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const params = new URLSearchParams({ limit: '100' });
        if (docCategory !== 'All') params.set('category', docCategory);
        if (docSearch.trim()) params.set('search', docSearch.trim());
        const res = await fetch(`/api/docs?${params.toString()}`);
        const data = await res.json();
        if (!cancelled && res.ok) {
          setDocs(data.documents || []);
        }
      } catch {
        // Ignore transient filter errors
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docCategory, docSearch]);

  const runRagQuery = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoadingQuery(true);
    setErrorMsg(null);
    setQuestion(trimmed);
    try {
      const res = await fetch('/api/a2ui/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: trimmed,
          k: 8,
          openaiApiKey: openaiKey.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Query failed');
      applyMessages(data.messages);
      setActiveTab('query');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingQuery(false);
    }
  };

  const inspectDoc = async (doc: DocEntry) => {
    setSelectedSource(doc.source);
    setErrorMsg(null);
    try {
      const params = new URLSearchParams({
        source: doc.source,
        title: doc.title,
      });
      const res = await fetch(`/api/a2ui/document?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Document load failed');
      applyMessages(data.messages);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  };

  type A2uiSurfaceProp = ComponentProps<typeof A2uiSurface>['surface'];

  // Resolve active SurfaceModel from MessageProcessor
  const overviewSurface = useMemo(
    () => processor.getSurface('f1-overview') as unknown as A2uiSurfaceProp | undefined,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [processor, surfaceTick],
  );
  const querySurface = useMemo(
    () => processor.getSurface('f1-rag-answer') as unknown as A2uiSurfaceProp | undefined,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [processor, surfaceTick],
  );
  const inspectorSurface = useMemo(
    () => processor.getSurface('f1-doc-inspector') as unknown as A2uiSurfaceProp | undefined,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [processor, surfaceTick],
  );

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="brand">
          <div className="brand-flag" />
          <div>
            <h1 className="brand-title">F1 RAG · Pit-Wall Dashboard</h1>
            <div className="brand-sub">
              A2UI v1.0 Generative UI · ChromaDB ({stats ? `${stats.totalChunks.toLocaleString()} chunks` : 'loading...'})
            </div>
          </div>
        </div>

        <div className="top-controls">
          <span className="status-pill">
            <span className="status-dot" />
            {stats ? `${stats.totalHtmlDocs} Docs · ${stats.collectionName}` : 'Connecting...'}
          </span>
          <button
            type="button"
            className={`wire-toggle-btn ${showWire ? 'active' : ''}`}
            onClick={() => setShowWire((v) => !v)}
          >
            <Code2 size={15} />
            {showWire ? 'Hide A2UI Wire JSON' : 'A2UI Wire JSON'}
          </button>
        </div>
      </header>

      <main className={`main-layout ${showWire ? 'with-inspector' : ''}`}>
        <div>
          <div className="nav-tabs">
            <div className="tab-group">
              <button
                type="button"
                className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                onClick={() => setActiveTab('overview')}
              >
                <Gauge size={15} />
                Corpus Telemetry
              </button>
              <button
                type="button"
                className={`tab-btn ${activeTab === 'query' ? 'active' : ''}`}
                onClick={() => setActiveTab('query')}
              >
                <Sparkles size={15} />
                RAG Query
              </button>
              <button
                type="button"
                className={`tab-btn ${activeTab === 'explorer' ? 'active' : ''}`}
                onClick={() => setActiveTab('explorer')}
              >
                <Database size={15} />
                Knowledge Explorer
              </button>
            </div>

            <div className="api-key-box">
              <input
                type="password"
                className="api-key-input"
                placeholder="Optional OpenAI Key (sk-...)"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                title="Optional: provide an OpenAI API key for GPT synthesis on top of ChromaDB retrieval"
              />
            </div>
          </div>

          {/* Always-accessible RAG query bar */}
          <section className="query-panel">
            <form
              className="query-form"
              onSubmit={(e) => {
                e.preventDefault();
                void runRagQuery(question);
              }}
            >
              <input
                type="text"
                className="query-input"
                placeholder="Ask anything about Formula 1 history, circuits, engines, or controversies..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
              <button type="submit" className="query-submit" disabled={loadingQuery}>
                <Search size={16} />
                {loadingQuery ? 'Retrieving...' : 'Ask F1 RAG'}
              </button>
            </form>

            {stats?.sampleQuestions && (
              <div className="sample-chips">
                {stats.sampleQuestions.map((sq) => (
                  <button
                    key={sq}
                    type="button"
                    className="sample-chip"
                    onClick={() => void runRagQuery(sq)}
                  >
                    {sq}
                  </button>
                ))}
              </div>
            )}
          </section>

          {errorMsg && (
            <div className="empty-state" style={{ borderColor: '#e10600', color: '#ff8580', marginBottom: '1rem' }}>
              {errorMsg}
            </div>
          )}

          {/* Overview Tab: A2UI Surface */}
          {activeTab === 'overview' && (
            <section className="surface-container">
              {overviewSurface ? (
                <A2uiSurface surface={overviewSurface} />
              ) : (
                <div className="empty-state">
                  <Activity size={24} style={{ marginBottom: '0.5rem' }} />
                  <div>Waiting for A2UI `f1-overview` surface...</div>
                </div>
              )}
            </section>
          )}

          {/* RAG Query Tab: A2UI Surface */}
          {activeTab === 'query' && (
            <section className="surface-container">
              {querySurface ? (
                <A2uiSurface surface={querySurface} />
              ) : (
                <div className="empty-state">
                  <Sparkles size={24} style={{ marginBottom: '0.5rem' }} />
                  <div>Ask an F1 question above or click a sample chip to generate an A2UI answer surface.</div>
                </div>
              )}
            </section>
          )}

          {/* Knowledge Explorer Tab */}
          {activeTab === 'explorer' && (
            <div className="explorer-grid">
              <aside className="explorer-sidebar">
                <input
                  type="text"
                  className="query-input"
                  style={{ padding: '0.5rem 0.75rem', fontSize: '0.84rem' }}
                  placeholder="Filter 979 F1 articles..."
                  value={docSearch}
                  onChange={(e) => setDocSearch(e.target.value)}
                />
                <select
                  className="query-input"
                  style={{ padding: '0.45rem 0.65rem', fontSize: '0.82rem' }}
                  value={docCategory}
                  onChange={(e) => setDocCategory(e.target.value)}
                >
                  <option value="All">All Categories</option>
                  {stats?.categories.map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name} ({c.count})
                    </option>
                  ))}
                </select>
                <div className="explorer-list">
                  {docs.map((doc) => (
                    <button
                      key={doc.source}
                      type="button"
                      className={`doc-item ${selectedSource === doc.source ? 'active' : ''}`}
                      onClick={() => void inspectDoc(doc)}
                    >
                      <span className="doc-item-title">{doc.title}</span>
                      <span className="doc-item-chunks">{doc.chunks}</span>
                    </button>
                  ))}
                </div>
              </aside>

              <section className="surface-container">
                {inspectorSurface ? (
                  <A2uiSurface surface={inspectorSurface} />
                ) : (
                  <div className="empty-state">
                    <FileText size={24} style={{ marginBottom: '0.5rem' }} />
                    <div>Select any F1 article on the left to inspect its ChromaDB chunks via A2UI.</div>
                  </div>
                )}
              </section>
            </div>
          )}
        </div>

        {showWire && (
          <aside className="wire-panel">
            <h3 className="wire-title">
              <span>A2UI v1.0 Wire Stream</span>
              <span className="f1-chart-badge">{wireLog.length} msg</span>
            </h3>
            <pre className="wire-pre">{JSON.stringify(wireLog, null, 2)}</pre>
          </aside>
        )}
      </main>
    </div>
  );
}
