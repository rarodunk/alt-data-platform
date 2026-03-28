"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { getCompanyOverview } from "@/lib/api";
import { CompanyOverview, ModelMetrics, ActualMetric, Prediction, SignalPoint } from "@/lib/types";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Area, ComposedChart,
} from "recharts";

interface MetricConfig { key: string; label: string; unit: string; }
interface Props { company: string; metrics: MetricConfig[]; note?: string; }

function fmt(v: number | null | undefined, unit: string, decimals = 1) {
  if (v == null) return "—";
  return `${v.toFixed(decimals)}${unit}`;
}

function pct(a: number, b: number) {
  return ((a - b) / Math.abs(b) * 100);
}

// ── Pearson correlation ───────────────────────────────────────────────────────
function pearsonCorr(xs: number[], ys: number[]): number {
  const n = Math.min(xs.length, ys.length);
  if (n < 3) return 0;
  const mx = xs.slice(0, n).reduce((a, b) => a + b, 0) / n;
  const my = ys.slice(0, n).reduce((a, b) => a + b, 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) {
    num += (xs[i] - mx) * (ys[i] - my);
    dx += (xs[i] - mx) ** 2;
    dy += (ys[i] - my) ** 2;
  }
  const denom = Math.sqrt(dx * dy);
  return denom < 1e-9 ? 0 : num / denom;
}

function dateToQuarter(date: string): string {
  const [y, m] = date.split("-").map(Number);
  return `Q${Math.ceil(m / 3)} ${y}`;
}

// ── Main chart ────────────────────────────────────────────────────────────────
function MainChart({ actuals, backtest, forward, unit }: {
  actuals: ActualMetric[];
  backtest: { quarter: string; predicted_value: number }[];
  forward: Prediction[];
  unit: string;
}) {
  const btMap = Object.fromEntries(backtest.map(r => [r.quarter, r.predicted_value]));
  const fwdMap = Object.fromEntries(forward.map(r => [r.quarter, { v: r.predicted_value, lo: r.confidence_lower, hi: r.confidence_upper }]));

  const quarters = [...actuals.map(a => a.quarter), ...forward.map(p => p.quarter)];
  const data = quarters.map(q => {
    const act = actuals.find(a => a.quarter === q);
    const fwd = fwdMap[q];
    return {
      quarter: q,
      actual: act?.value ?? null,
      model: act ? (btMap[q] ?? null) : null,
      forecast: fwd?.v ?? null,
      lo: fwd?.lo ?? null,
      hi: fwd?.hi ?? null,
    };
  });

  const lastActualQ = [...actuals].sort((a, b) => b.period_end.localeCompare(a.period_end))[0]?.quarter;

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const items = payload.filter((p: any) => p.value != null && !["lo", "hi"].includes(p.dataKey));
    return (
      <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 14px", fontSize: 13 }}>
        <div style={{ fontWeight: 600, marginBottom: 6, color: "var(--ink)" }}>{label}</div>
        {items.map((p: any) => (
          <div key={p.dataKey} style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
            <span style={{ color: "var(--muted)" }}>{p.name}</span>
            <span style={{ fontWeight: 600, color: p.color }}>{Number(p.value).toFixed(1)}{unit}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid stroke="var(--line)" strokeDasharray="4 4" vertical={false} />
        <XAxis dataKey="quarter" tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}${unit}`} width={52} />
        <Tooltip content={<CustomTooltip />} />
        <Area dataKey="hi" stroke="none" fill="#61aff4" fillOpacity={0.1} legendType="none" name="hi" connectNulls />
        <Area dataKey="lo" stroke="none" fill="var(--panel)" fillOpacity={1} legendType="none" name="lo" connectNulls />
        <Line dataKey="actual"   name="Reported"       stroke="#363737" strokeWidth={2.5} dot={false} connectNulls />
        <Line dataKey="model"    name="Model Estimate" stroke="#61aff4" strokeWidth={2}   dot={false} strokeDasharray="7 4" connectNulls />
        <Line dataKey="forecast" name="Forecast"       stroke="#61aff4" strokeWidth={2}   dot={{ fill: "#61aff4", r: 3, strokeWidth: 0 }} strokeDasharray="7 4" connectNulls />
        {lastActualQ && <ReferenceLine x={lastActualQ} stroke="var(--line)" strokeWidth={1.5} strokeDasharray="6 3" />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── Feature importance bar chart ──────────────────────────────────────────────
function FeatureImportanceChart({ importance }: { importance: Record<string, number> }) {
  const sorted = Object.entries(importance).sort(([, a], [, b]) => b - a).slice(0, 12);
  const max = sorted[0]?.[1] ?? 1;
  const altDataTotal = Object.entries(importance)
    .filter(([k]) => k.startsWith("trend_"))
    .reduce((s, [, v]) => s + v, 0);
  const total = Object.values(importance).reduce((s, v) => s + v, 0);

  const category = (name: string): "alt-data" | "momentum" | "seasonality" => {
    if (name.startsWith("trend_")) return "alt-data";
    if (name.startsWith("is_")) return "seasonality";
    return "momentum";
  };
  const catColor = { "alt-data": "#61aff4", "momentum": "#363737", "seasonality": "#2563eb" };
  const catLabel = { "alt-data": "Alt Data", "momentum": "Momentum/Lag", "seasonality": "Seasonality" };

  const formatName = (name: string) =>
    name.replace(/^trend_/, "● ").replace(/_lag(\d+)$/, " (L$1)").replace(/_roll(\d+)$/, " (MA$1)").replace(/_/g, " ");

  return (
    <div>
      <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 12 }}>
        <div className="panel" style={{ padding: "8px 14px", flex: 1, textAlign: "center" }}>
          <div className="kpi-label">Alt Data Share</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: "#61aff4" }}>{((altDataTotal / total) * 100).toFixed(0)}%</div>
          <div className="kpi-sub">of model weight</div>
        </div>
        <div className="panel" style={{ padding: "8px 14px", flex: 1, textAlign: "center" }}>
          <div className="kpi-label">Momentum Share</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: "#363737" }}>{(((total - altDataTotal) / total) * 100).toFixed(0)}%</div>
          <div className="kpi-sub">of model weight</div>
        </div>
      </div>

      {sorted.map(([name, val]) => {
        const cat = category(name);
        const color = catColor[cat];
        return (
          <div key={name} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
            <div style={{ fontSize: 11, color: "var(--muted)", width: 160, textAlign: "right", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flexShrink: 0 }}>
              {formatName(name)}
            </div>
            <div style={{ flex: 1, height: 16, background: "var(--line)", borderRadius: 3, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${(val / max) * 100}%`, background: color, borderRadius: 3, opacity: 0.85 }} />
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color, width: 38, textAlign: "right", flexShrink: 0 }}>
              {val.toFixed(1)}%
            </div>
          </div>
        );
      })}

      <div style={{ display: "flex", gap: 14, marginTop: 10, fontSize: 11, color: "var(--muted)", flexWrap: "wrap" }}>
        {(Object.entries(catLabel) as [keyof typeof catLabel, string][]).map(([cat, label]) => (
          <span key={cat}>
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: catColor[cat], marginRight: 4 }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Signal correlation cards ──────────────────────────────────────────────────
function SignalCorrelations({ signals, actuals }: {
  signals: SignalPoint[];
  actuals: ActualMetric[];
}) {
  const [lagMode, setLagMode] = useState<0 | 1>(0); // 0 = same-Q, 1 = 1Q lead

  // Build quarterly averages per (source, metric_name)
  const signalKeys = useMemo(() => {
    const keys = new Set<string>();
    signals.forEach(s => keys.add(`${s.source}::${s.metric_name}`));
    return Array.from(keys);
  }, [signals]);

  const quarterlySignals = useMemo(() => {
    const out: Record<string, Record<string, number>> = {};
    for (const key of signalKeys) {
      const [source, metric_name] = key.split("::");
      const filtered = signals.filter(s => s.source === source && s.metric_name === metric_name);
      const byQ: Record<string, number[]> = {};
      for (const s of filtered) {
        const q = dateToQuarter(s.date);
        if (!byQ[q]) byQ[q] = [];
        byQ[q].push(s.value);
      }
      const avg: Record<string, number> = {};
      for (const [q, vals] of Object.entries(byQ)) {
        avg[q] = vals.reduce((a, b) => a + b, 0) / vals.length;
      }
      out[key] = avg;
    }
    return out;
  }, [signals, signalKeys]);

  // Compute correlations and build signal card data
  const signalCards = useMemo(() => {
    return signalKeys.map(key => {
      const [source, metric_name] = key.split("::");
      const qAvgs = quarterlySignals[key];

      // Align signal quarters with actual quarters (with optional lag)
      const actualQuarters = actuals.map(a => a.quarter);
      const pairs: [number, number][] = [];
      for (let i = lagMode; i < actuals.length; i++) {
        const aq = actualQuarters[i];
        const sq = actualQuarters[i - lagMode];
        if (sq && qAvgs[sq] != null) {
          pairs.push([qAvgs[sq], actuals[i].value]);
        }
      }

      const corr = pairs.length >= 3
        ? pearsonCorr(pairs.map(p => p[0]), pairs.map(p => p[1]))
        : 0;

      // Recent signal values for sparkline (last 52 weeks or all)
      const recentSignal = signals
        .filter(s => s.source === source && s.metric_name === metric_name)
        .sort((a, b) => a.date.localeCompare(b.date))
        .slice(-52);

      const recent = recentSignal.slice(-8).map(s => s.value);
      const trend = recent.length >= 2 ? recent[recent.length - 1] - recent[0] : 0;

      const friendlyName: Record<string, string> = {
        interest_value: "Search Interest",
        normalized_value: "Search Index (norm.)",
        post_count: "Post Volume",
        comment_count: "Comment Volume",
        sentiment_score: "Sentiment Score",
        mention_count: "Brand Mentions",
        avg_score: "Avg Post Score",
        rating_count: "App Ratings (cumulative)",
        avg_rating: "App Store Rating",
        flight_count: "Weekly Flight Count",
        flight_hours: "Weekly Flight Hours",
        unique_airports: "Unique Airports",
        utilization_score: "Fleet Utilization",
      };

      const sourceLabel: Record<string, string> = {
        google_trends: "Google Trends",
        reddit: "Reddit",
        appstore: "App Store (iOS)",
        opensky: "OpenSky Network",
        opensky_proxy: "OpenSky (estimated)",
      };

      const name = friendlyName[metric_name] ?? metric_name.replace(/_/g, " ");
      const srcLabel = sourceLabel[source] ?? source;

      return { key, source, metric_name, name, srcLabel, corr, recentSignal, trend, recent };
    }).sort((a, b) => Math.abs(b.corr) - Math.abs(a.corr));
  }, [signalKeys, quarterlySignals, actuals, signals, lagMode]);

  if (!signalCards.length) return <div style={{ color: "var(--muted)", fontSize: 13 }}>No signal data.</div>;

  const corrColor = (r: number) => {
    const abs = Math.abs(r);
    if (abs >= 0.7) return r > 0 ? "var(--good)" : "var(--bad)";
    if (abs >= 0.4) return "#61aff4";
    return "var(--muted)";
  };

  const corrLabel = (r: number) => {
    const abs = Math.abs(r);
    const dir = r >= 0 ? "positive" : "negative";
    if (abs >= 0.7) return `Strong ${dir}`;
    if (abs >= 0.4) return `Moderate ${dir}`;
    return "Weak";
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 14, alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "var(--muted)" }}>Correlation mode:</span>
        {([0, 1] as const).map(l => (
          <button key={l} className={lagMode === l ? "btn btn-primary" : "btn"} style={{ fontSize: 11, padding: "4px 10px" }}
            onClick={() => setLagMode(l)}>
            {l === 0 ? "Same quarter" : "1Q lead (signal → next Q actual)"}
          </button>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
        {signalCards.map(card => {
          const miniData = card.recentSignal.slice(-24);
          const minV = Math.min(...miniData.map(s => s.value));
          const maxV = Math.max(...miniData.map(s => s.value));
          const range = maxV - minV || 1;

          // SVG sparkline points
          const W = 200, H = 40;
          const pts = miniData.map((s, i) => {
            const x = (i / Math.max(miniData.length - 1, 1)) * W;
            const y = H - 4 - ((s.value - minV) / range) * (H - 8);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
          }).join(" ");

          return (
            <div key={card.key} className="panel" style={{ padding: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)" }}>{card.name}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>{card.srcLabel}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: corrColor(card.corr) }}>
                    {card.corr >= 0 ? "+" : ""}{card.corr.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 10, color: corrColor(card.corr) }}>{corrLabel(card.corr)}</div>
                </div>
              </div>

              {miniData.length > 1 && (
                <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: "block", marginBottom: 6 }}>
                  <polyline points={pts} fill="none" stroke={corrColor(card.corr)} strokeWidth="1.5" opacity="0.7" />
                  {miniData.length > 0 && (
                    <circle
                      cx={((miniData.length - 1) / Math.max(miniData.length - 1, 1)) * W}
                      cy={H - 4 - ((miniData[miniData.length - 1].value - minV) / range) * (H - 8)}
                      r="3" fill={corrColor(card.corr)}
                    />
                  )}
                </svg>
              )}

              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)" }}>
                <span>
                  {card.trend > 0 ? "↑" : card.trend < 0 ? "↓" : "→"}{" "}
                  {Math.abs(card.trend) < 0.01 ? "Flat" : `${card.trend > 0 ? "+" : ""}${card.trend.toFixed(1)}`} (8-week)
                </span>
                <span>r² = {(card.corr ** 2).toFixed(2)}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 10, fontSize: 11, color: "var(--muted)" }}>
        Pearson r computed on quarterly averages of weekly signal data vs quarterly actuals. |r| ≥ 0.7 = strong, 0.4–0.7 = moderate, &lt;0.4 = weak.
      </div>
    </div>
  );
}

// ── Signal detail chart: overlay signal on quarterly actuals ──────────────────
function SignalOverlayChart({ signals, actuals, signalKey, unit }: {
  signals: SignalPoint[];
  actuals: ActualMetric[];
  signalKey: string;
  unit: string;
}) {
  const [source, metric_name] = signalKey.split("::");
  const filtered = signals
    .filter(s => s.source === source && s.metric_name === metric_name)
    .sort((a, b) => a.date.localeCompare(b.date));

  if (!filtered.length) return null;

  const data = filtered.map(s => ({ date: s.date, signal: s.value }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid stroke="var(--line)" strokeDasharray="4 4" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} interval={12} />
        <YAxis tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} width={32} />
        <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
        <Line dataKey="signal" stroke="#61aff4" strokeWidth={1.5} dot={false} name={metric_name.replace(/_/g, " ")} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Data table ────────────────────────────────────────────────────────────────
function DataTable({ actuals, backtest, forward, unit }: {
  actuals: ActualMetric[];
  backtest: { quarter: string; actual_value: number; predicted_value: number; pct_error: number }[];
  forward: Prediction[];
  unit: string;
}) {
  const btMap = Object.fromEntries(backtest.map(r => [r.quarter, r]));
  const rows = [
    ...actuals.map(a => {
      const bt = btMap[a.quarter];
      const prevActual = actuals.find(x => {
        const [q, y] = a.quarter.split(" ");
        const pq = parseInt(q.slice(1)), py = parseInt(y);
        const [pqn, pyn] = pq === 1 ? [4, py - 1] : [pq - 1, py];
        return x.quarter === `Q${pqn} ${pyn}`;
      });
      const qoq = prevActual ? pct(a.value, prevActual.value) : null;
      return { quarter: a.quarter, period_end: a.period_end, reported: a.value, model: bt?.predicted_value ?? null, error: bt?.pct_error ?? null, qoq, source: a.source, isForecast: false };
    }),
    ...forward.map(p => ({
      quarter: p.quarter, period_end: p.period_end, reported: null, model: p.predicted_value, error: null, qoq: null, source: "forecast", isForecast: true,
    })),
  ].reverse();

  return (
    <div style={{ overflowY: "auto", maxHeight: 480 }}>
      <table>
        <thead>
          <tr>
            <th>Quarter</th><th>Period End</th>
            <th>Reported{unit ? ` (${unit.trim()})` : ""}</th>
            <th>Model Est.</th><th>Error %</th><th>QoQ %</th><th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.quarter} style={r.isForecast ? { background: "#f0f8ff", fontStyle: "italic" } : {}}>
              <td style={{ fontWeight: 600 }}>{r.quarter}</td>
              <td style={{ color: "var(--muted)" }}>{r.period_end}</td>
              <td>{r.reported != null ? r.reported.toFixed(1) : <span style={{ color: "var(--muted)" }}>—</span>}</td>
              <td style={{ color: "var(--accent2)" }}>{r.model != null ? r.model.toFixed(1) : "—"}</td>
              <td>{r.error != null ? <span className={Math.abs(r.error) < 5 ? "positive" : Math.abs(r.error) < 15 ? "" : "negative"}>{r.error > 0 ? "+" : ""}{r.error.toFixed(1)}%</span> : "—"}</td>
              <td>{r.qoq != null ? <span className={r.qoq >= 0 ? "positive" : "negative"}>{r.qoq >= 0 ? "+" : ""}{r.qoq.toFixed(1)}%</span> : "—"}</td>
              <td style={{ color: "var(--muted)", fontSize: 12 }}>{r.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function CompanyPage({ company, metrics, note }: Props) {
  const [data, setData] = useState<CompanyOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeMetric, setActiveMetric] = useState(metrics[0].key);
  const [refreshing, setRefreshing] = useState(false);
  const [signalTab, setSignalTab] = useState<"importance" | "correlations">("correlations");
  const [pollCount, setPollCount] = useState(0);

  const load = useCallback(() => {
    setLoading(true);
    getCompanyOverview(company)
      .then(d => { setData(d); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [company]);

  useEffect(() => { load(); }, [load]);

  // Auto-poll until both backtest and forward predictions are present.
  // Continues even on error (backend cold start can take 50s on Render free tier).
  useEffect(() => {
    const hasBacktest = (data?.backtest_results?.length ?? 0) > 0;
    const hasFwd = (data?.forward_predictions?.length ?? 0) > 0;
    if ((!hasBacktest || !hasFwd) && !refreshing) {
      // Back off slightly each poll: 15s, 20s, 25s … capped at 30s
      const delay = Math.min(15000 + pollCount * 5000, 30000);
      const t = setTimeout(() => { setPollCount(c => c + 1); load(); }, delay);
      return () => clearTimeout(t);
    } else {
      setPollCount(0);
    }
  }, [data, error, load, refreshing, pollCount]);

  const cm = metrics.find(m => m.key === activeMetric) ?? metrics[0];
  const mm: ModelMetrics | null = data?.model_metrics?.[activeMetric] ?? null;

  const metricActuals = (data?.actuals ?? [])
    .filter(a => a.metric_name === activeMetric)
    .sort((a, b) => a.period_end.localeCompare(b.period_end));

  const backtestRows = (data?.backtest_results ?? []).filter(r => r.metric_name === activeMetric);
  const fwdPreds = (data?.forward_predictions ?? [])
    .filter(p => p.metric_name === activeMetric)
    .sort((a, b) => a.period_end.localeCompare(b.period_end));

  const lastActual = metricActuals.at(-1);
  const prevActual = metricActuals.at(-2);
  const prevYearActual = metricActuals.at(-5);
  const nextQ = fwdPreds[0];

  const qoqPct = lastActual && prevActual ? pct(lastActual.value, prevActual.value) : null;
  const yoyPct = lastActual && prevYearActual ? pct(lastActual.value, prevYearActual.value) : null;
  const impliedPct = nextQ && lastActual ? pct(nextQ.predicted_value, lastActual.value) : null;

  async function handleRefresh() {
    setRefreshing(true);
    const prevRunAt = data?.model_metrics?.[metrics[0].key]?.run_at ?? null;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"}/${company}/refresh`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error(await res.text());
    } catch (e: any) {
      setError(e.message);
      setRefreshing(false);
      return;
    }

    // Poll every 5s until model run_at changes (models re-ran), or timeout after 90s
    const deadline = Date.now() + 90_000;
    const poll = async () => {
      try {
        const fresh = await getCompanyOverview(company);
        const newRunAt = fresh.model_metrics?.[metrics[0].key]?.run_at ?? null;
        if (newRunAt && newRunAt !== prevRunAt) {
          setData(fresh);
          setRefreshing(false);
          return;
        }
      } catch {}
      if (Date.now() < deadline) {
        setTimeout(poll, 5000);
      } else {
        load();
        setRefreshing(false);
      }
    };
    setTimeout(poll, 8000);
  }

  return (
    <div style={{ maxWidth: 1320, margin: "0 auto", padding: "24px 16px" }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <a href="/" style={{ fontSize: 13, color: "var(--accent)", textDecoration: "none" }}>← All</a>
            <h1 style={{ fontSize: 26, fontWeight: 700, margin: 0 }}>{data?.name ?? company}</h1>
            <span style={{ fontSize: 16, fontWeight: 600, color: "var(--muted)" }}>{data?.ticker}</span>
          </div>
          {data?.description && <p style={{ fontSize: 13, color: "var(--muted)", margin: "4px 0 0" }}>{data.description}</p>}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {metrics.length > 1 && metrics.map(m => (
            <button key={m.key} className={activeMetric === m.key ? "btn btn-primary" : "btn"} onClick={() => setActiveMetric(m.key)}>
              {m.label}
            </button>
          ))}
          <button className="btn btn-primary" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Refresh Data"}
          </button>
        </div>
      </div>

      {/* Status bar */}
      {mm && (
        <div className="panel" style={{ padding: "8px 16px", marginBottom: 16, fontSize: 13, color: "var(--muted)" }}>
          Model: <strong style={{ color: "var(--ink)" }}>{mm.model_type}</strong>
          {" · "}Trained through <strong style={{ color: "var(--ink)" }}>{metricActuals.at(-1)?.quarter}</strong>
          {" · "}<strong style={{ color: "var(--ink)" }}>{metricActuals.length}</strong> actuals
          {mm.mape != null && <> · MAPE <strong style={{ color: mm.mape < 10 ? "var(--good)" : "var(--accent2)" }}>{mm.mape.toFixed(1)}%</strong></>}
          {mm.directional_accuracy != null && <> · Dir. Acc. <strong style={{ color: mm.directional_accuracy >= 65 ? "var(--good)" : "var(--accent2)" }}>{mm.directional_accuracy.toFixed(0)}%</strong></>}
          {mm.run_at && <> · Run {new Date(mm.run_at).toLocaleDateString()}</>}
        </div>
      )}

      {note && <div className="panel" style={{ padding: "8px 16px", marginBottom: 16, fontSize: 12, color: "var(--muted)" }}>{note}</div>}
      {error && (
        <div className="panel" style={{ padding: "10px 16px", marginBottom: 16, color: "var(--muted)", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>Backend warming up (Render cold start) — retrying automatically…</span>
          <button className="btn" style={{ marginLeft: 16, fontSize: 12, padding: "4px 10px" }} onClick={load}>Retry now</button>
        </div>
      )}
      {loading && <div style={{ color: "var(--muted)", fontSize: 14, padding: 48, textAlign: "center" }}>Loading…</div>}
      {!loading && data && (data.backtest_results?.length ?? 0) === 0 && (
        <div className="panel" style={{ padding: "12px 16px", marginBottom: 16, fontSize: 13, color: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>⏳ Models training on first load — checking every {Math.min(15 + pollCount * 5, 30)}s{pollCount > 0 ? ` (attempt ${pollCount + 1})` : ""}…</span>
          <button className="btn" style={{ marginLeft: 16, fontSize: 12, padding: "4px 10px" }} onClick={() => { setPollCount(0); load(); }}>Check now</button>
        </div>
      )}

      {!loading && !error && data && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16 }}>

          {/* KPI cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
            {[
              { label: "Last Actual", value: fmt(lastActual?.value, cm.unit), sub: lastActual?.quarter },
              { label: `${nextQ?.quarter ?? "Next Q"} Forecast`, value: fmt(nextQ?.predicted_value, cm.unit), sub: impliedPct != null ? `${impliedPct >= 0 ? "+" : ""}${impliedPct.toFixed(1)}% implied` : undefined, highlight: impliedPct != null ? (impliedPct >= 0 ? "var(--good)" : "var(--bad)") : undefined },
              { label: "QoQ Growth", value: qoqPct != null ? `${qoqPct >= 0 ? "+" : ""}${qoqPct.toFixed(1)}%` : "—", sub: `${prevActual?.quarter} → ${lastActual?.quarter}`, highlight: qoqPct != null ? (qoqPct >= 0 ? "var(--good)" : "var(--bad)") : undefined },
              { label: "YoY Growth", value: yoyPct != null ? `${yoyPct >= 0 ? "+" : ""}${yoyPct.toFixed(1)}%` : "—", sub: `vs ${prevYearActual?.quarter}`, highlight: yoyPct != null ? (yoyPct >= 0 ? "var(--good)" : "var(--bad)") : undefined },
            ].map(card => (
              <div key={card.label} className="panel" style={{ padding: 16 }}>
                <div className="kpi-label">{card.label}</div>
                <div className="kpi-value" style={card.highlight ? { color: card.highlight } : {}}>{card.value}</div>
                {card.sub && <div className="kpi-sub">{card.sub}</div>}
              </div>
            ))}
          </div>

          {/* Chart + forward forecasts */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "start" }}>
            <div className="panel" style={{ padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{cm.label} — Reported vs Model</div>
                <div style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--muted)" }}>
                  <span><span style={{ display: "inline-block", width: 20, height: 2, background: "#363737", verticalAlign: "middle", marginRight: 4 }} />Reported</span>
                  <span><span style={{ display: "inline-block", width: 20, height: 2, background: "#61aff4", borderTop: "2px dashed #61aff4", verticalAlign: "middle", marginRight: 4 }} />Model</span>
                </div>
              </div>
              <MainChart actuals={metricActuals} backtest={backtestRows} forward={fwdPreds} unit={cm.unit} />
            </div>

            {fwdPreds.length > 0 && (
              <div className="panel" style={{ padding: 16, minWidth: 200 }}>
                <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted)", marginBottom: 12 }}>Forward Forecast</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {fwdPreds.map(p => {
                    const g = lastActual ? pct(p.predicted_value, lastActual.value) : null;
                    const [q, y] = p.quarter.split(" ");
                    const priorYearActual = metricActuals.find(a => a.quarter === `${q} ${parseInt(y) - 1}`);
                    const yoy = priorYearActual != null ? pct(p.predicted_value, priorYearActual.value) : null;
                    return (
                      <div key={p.quarter} style={{ borderBottom: "1px solid var(--line)", paddingBottom: 10 }}>
                        <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 2 }}>{p.quarter}</div>
                        <div style={{ fontSize: 22, fontWeight: 700, color: "#61aff4" }}>{p.predicted_value.toFixed(1)}{cm.unit}</div>
                        {p.confidence_lower != null && (
                          <div style={{ fontSize: 11, color: "var(--muted)" }}>[{p.confidence_lower.toFixed(1)} – {p.confidence_upper?.toFixed(1)}]</div>
                        )}
                        <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
                          {g != null && <div style={{ fontSize: 11, fontWeight: 600, color: g >= 0 ? "var(--good)" : "var(--bad)" }}>{g >= 0 ? "+" : ""}{g.toFixed(1)}% vs last</div>}
                          {yoy != null && <div style={{ fontSize: 11, fontWeight: 600, color: yoy >= 0 ? "var(--good)" : "var(--bad)" }}>{yoy >= 0 ? "+" : ""}{yoy.toFixed(1)}% YoY</div>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* ── Alt Data Signals section ── */}
          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "14px 20px 0", borderBottom: "1px solid var(--line)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>Alt Data Signals</span>
                  <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 8 }}>
                    {data.signals?.length ?? 0} weekly observations · {new Set(data.signals?.map(s => `${s.source}::${s.metric_name}`)).size} series
                  </span>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className={signalTab === "correlations" ? "btn btn-primary" : "btn"} style={{ fontSize: 12 }} onClick={() => setSignalTab("correlations")}>
                    Correlations
                  </button>
                  <button className={signalTab === "importance" ? "btn btn-primary" : "btn"} style={{ fontSize: 12 }} onClick={() => setSignalTab("importance")}>
                    Feature Importance
                  </button>
                </div>
              </div>
            </div>

            <div style={{ padding: 20 }}>
              {signalTab === "correlations" && (
                <SignalCorrelations signals={data.signals ?? []} actuals={metricActuals} />
              )}
              {signalTab === "importance" && mm?.feature_importance && Object.keys(mm.feature_importance).length > 0 && (
                <FeatureImportanceChart importance={mm.feature_importance} />
              )}
              {signalTab === "importance" && (!mm?.feature_importance || Object.keys(mm.feature_importance ?? {}).length === 0) && (
                <div style={{ color: "var(--muted)", fontSize: 13 }}>No feature importance data for this metric.</div>
              )}
            </div>
          </div>

          {/* Data table */}
          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "14px 16px 10px", borderBottom: "1px solid var(--line)" }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Quarterly Data</span>
              <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 8 }}>
                {metricActuals.length} actuals · {fwdPreds.length} forecast quarters
              </span>
            </div>
            <DataTable actuals={metricActuals} backtest={backtestRows} forward={fwdPreds} unit={cm.unit} />
          </div>

        </div>
      )}
    </div>
  );
}
