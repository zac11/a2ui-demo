import { createComponentImplementation, type ReactCatalogComponent } from '@a2ui/react';
import { Catalog, CommonSchemas } from '@a2ui/web_core/v1_0';
import { z } from 'zod';

export const F1_CATALOG_ID = 'https://a2ui.org/custom/f1-rag/v1/catalog.json';

const F1StatTileApi = {
  name: 'F1StatTile',
  schema: z.object({
    label: z.string(),
    value: CommonSchemas.DynamicString,
    sublabel: CommonSchemas.DynamicString.optional(),
    accent: z.enum(['red', 'teal', 'amber', 'blue']).optional(),
  }),
};

const F1StatTile = createComponentImplementation(F1StatTileApi, ({ props }) => {
  const accent = props.accent ?? 'red';
  return (
    <div className={`f1-stat-tile f1-accent-${accent}`}>
      <div className="f1-stat-label">{props.label}</div>
      <div className="f1-stat-value">{String(props.value ?? '—')}</div>
      {props.sublabel && <div className="f1-stat-sublabel">{String(props.sublabel)}</div>}
    </div>
  );
});

const F1BarChartApi = {
  name: 'F1BarChart',
  schema: z.object({
    title: z.string(),
    items: z.union([
      z.array(z.object({ name: z.string(), count: z.number() })),
      CommonSchemas.DataBinding,
    ]),
  }),
};

const F1BarChart = createComponentImplementation(F1BarChartApi, ({ props }) => {
  const items = Array.isArray(props.items)
    ? (props.items as Array<{ name: string; count: number }>)
    : [];
  const maxCount = Math.max(...items.map((i) => i.count), 1);

  return (
    <div className="f1-chart-card">
      <div className="f1-chart-header">
        <span className="f1-chart-title">{props.title}</span>
        <span className="f1-chart-badge">CHROMA INDEX</span>
      </div>
      <div className="f1-bar-list">
        {items.map((item, idx) => {
          const pct = Math.max(4, Math.round((item.count / maxCount) * 100));
          return (
            <div key={item.name} className="f1-bar-row">
              <div className="f1-bar-meta">
                <span className="f1-bar-name">{item.name}</span>
                <span className="f1-bar-count">{item.count} docs</span>
              </div>
              <div className="f1-bar-track">
                <div
                  className={`f1-bar-fill f1-bar-color-${idx % 4}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

const F1PassageCardApi = {
  name: 'F1PassageCard',
  schema: z.object({
    rank: z.number(),
    title: z.string(),
    source: z.string(),
    category: z.string(),
    score: z.number(),
    content: z.string(),
    action: CommonSchemas.Action.optional(),
  }),
};

const F1PassageCard = createComponentImplementation(
  F1PassageCardApi,
  ({ props }) => {
    const handleInspect = () => {
      if (props.action) {
        void props.action();
      }
    };

    return (
      <div className="f1-passage-card">
        <div className="f1-passage-top">
          <div className="f1-passage-title-group">
            <span className="f1-passage-rank">#{props.rank}</span>
            <span className="f1-passage-title">{props.title}</span>
            <span className="f1-passage-cat">{props.category}</span>
          </div>
          <div className="f1-passage-actions">
            <span className="f1-passage-score">
              BM25 {typeof props.score === 'number' ? props.score.toFixed(2) : props.score}
            </span>
            {props.action && (
              <button
                type="button"
                className="f1-inspect-btn"
                onClick={handleInspect}
              >
                Inspect Source
              </button>
            )}
          </div>
        </div>
        <p className="f1-passage-content">{props.content}</p>
        <div className="f1-passage-source">{props.source}</div>
      </div>
    );
  },
);

export const f1Catalog = new Catalog<ReactCatalogComponent>(
  F1_CATALOG_ID,
  '1.0',
  [F1StatTile, F1BarChart, F1PassageCard],
);
