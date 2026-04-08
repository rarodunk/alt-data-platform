"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { getChessTrends, getChessAppstore, getChessSummary } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────
interface TrendPoint { date: string; interest_value: number; }
interface RatingPoint { date: string; rating_count: number; avg_rating: number; }
interface LiveApp {
  date: string; app: string; app_name: string;
  rating_count: number; avg_rating: number;
}
interface Summary {
  as_of: string | null;
  trends: {
    chess_com: { latest_interest: number | null; peak_interest: number | null };
    duolingo_chess: { latest_interest: number | null; peak_interest: number | null };
  };
  appstore: {
    chess_com: { rating_count: number; avg_rating: number; app_name: string } | null;
    duolingo: { rating_count: number; avg_rating: number; app_name: string } | null;
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(decimals)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(decimals)}K`;
  return n.toFixed(decimals);
}

function fmtDate(d: string): string {
  return d.slice(0, 7); // YYYY-MM
}

// Sub-sample to ~monthly for chart readability (weekly data → every ~4 points)
function thinSeries<T extends { date: string }>(arr: T[], step = 4): T[] {
  return arr.filter((_, i) => i % step === 0);
}

// Merge two date-aligned series into chart data
function mergeTrends(
  chess: TrendPoint[],
  duolingo: TrendPoint[]
): { date: string; chess_com: number | null; duolingo_chess: number | null }[] {
  const map = new Map<string, { chess_com: number | null; duolingo_chess: number | null }>();
  chess.forEach(d => {
    const e = map.get(d.date) ?? { chess_com: null, duolingo_chess: null };
    e.chess_com = d.interest_value;
    map.set(d.date, e);
  });
  duolingo.forEach(d => {
    const e = map.get(d.date) ?? { chess_com: null, duolingo_chess: null };
    e.duolingo_chess = d.interest_value;
    map.set(d.date, e);
  });
  return Array.from(map.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, v]) => ({ date, ...v }));
}

function mergeRatings(
  chess: RatingPoint[],
  duolingo: RatingPoint[]
): { date: string; chess_com: number | null; duolingo: number | null }[] {
  const map = new Map<string, { chess_com: number | null; duolingo: number | null }>();
  chess.forEach(d => {
    const e = map.get(d.date) ?? { chess_com: null, duolingo: null };
    e.chess_com = d.rating_count;
    map.set(d.date, e);
  });
  duolingo.forEach(d => {
    const e = map.get(d.date) ?? { chess_com: null, duolingo: null };
    e.duolingo = d.rating_count;
    map.set(d.date, e);
  });
  return Array.from(map.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, v]) => ({ date, ...v }));
}

// ── Custom tooltip ─────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label, unit = "" }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "var(--panel)", border: "1px solid var(--line)",
      borderRadius: 6, padding: "10px 14px", fontSize: 13,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 6, color: "var(--ink)" }}>{label}</div>
      {payload.map((p: any) => p.value != null && (
        <div key={p.dataKey} style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <span style={{ color: "var(--muted)" }}>{p.name}</span>
          <span style={{ fontWeight: 600, color: p.color }}>
            {unit === "M" ? `${(p.value / 1_000_000).toFixed(2)}M`
              : unit === "idx" ? p.value.toFixed(1)
              : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="panel" style={{ padding: "16px 20px", flex: 1, minWidth: 160 }}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={color ? { color } : {}}>{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ChessTrackerPage() {
  const [trendsData, setTrendsData] = useState<{
    chess_com: TrendPoint[]; duolingo_chess: TrendPoint[];
  } | null>(null);
  const [appstoreData, setAppstoreData] = useState<{
    historical: { chess_com: RatingPoint[]; duolingo: RatingPoint[] };
    live: LiveApp[];
  } | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [t, a, s] = await Promise.all([
        getChessTrends(),
        getChessAppstore(),
        getChessSummary(),
      ]);
      setTrendsData({ chess_com: t.chess_com, duolingo_chess: t.duolingo_chess });
      setAppstoreData({ historical: a.historical, live: a.live });
      setSummary(s);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  // Derived chart data
  const trendChartData = trendsData
    ? thinSeries(mergeTrends(trendsData.chess_com, trendsData.duolingo_chess), 1)
    : [];

  const ratingChartData = appstoreData
    ? thinSeries(mergeRatings(appstoreData.historical.chess_com, appstoreData.historical.duolingo), 2)
    : [];

  const liveChessCom = appstoreData?.live.find(d => d.app === "chess_com");
  const liveDuolingo = appstoreData?.live.find(d => d.app === "duolingo");

  // Most recent 10 trend entries for table
  const recentTrends: { date: string; chess_com: number | null; duolingo_chess: number | null }[] =
    trendChartData.slice(-10).reverse();

  const CHESS_COLOR = "#4a90e2";
  const DUOLINGO_COLOR = "#58cc02";

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "40px 16px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28, gap: 16, flexWrap: "wrap" }}>
        <div>
          <Link href="/" style={{ fontSize: 12, color: "var(--muted)", textDecoration: "none", letterSpacing: "0.05em" }}>
            ← Alt Data Platform
          </Link>
          <h1 style={{ fontSize: 26, fontWeight: 700, margin: "8px 0 4px" }}>
            Chess.com vs Duolingo Chess
          </h1>
          <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>
            Web visit proxy (Google Trends) · App download proxy (App Store ratings)
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleRefresh}
          disabled={refreshing || loading}
          style={{ marginTop: 8, whiteSpace: "nowrap" }}
        >
          {refreshing ? "Refreshing…" : "Refresh Data"}
        </button>
      </div>

      {error && (
        <div className="panel" style={{ padding: "12px 16px", marginBottom: 20, color: "var(--bad)", fontSize: 13 }}>
          Unable to reach backend — {error}
        </div>
      )}

      {loading ? (
        <div style={{ color: "var(--muted)", fontSize: 14, padding: "40px 0", textAlign: "center" }}>
          Loading chess tracker data…
        </div>
      ) : (
        <>
          {/* ── KPI strip ───────────────────────────────────────────────────── */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
            <KpiCard
              label="Chess.com — Search Interest"
              value={summary?.trends.chess_com.latest_interest != null
                ? `${summary.trends.chess_com.latest_interest.toFixed(0)} / 100` : "—"}
              sub={`Peak: ${summary?.trends.chess_com.peak_interest?.toFixed(0) ?? "—"}`}
              color={CHESS_COLOR}
            />
            <KpiCard
              label="Duolingo Chess — Search Interest"
              value={summary?.trends.duolingo_chess.latest_interest != null
                ? `${summary.trends.duolingo_chess.latest_interest.toFixed(0)} / 100` : "—"}
              sub={`Peak: ${summary?.trends.duolingo_chess.peak_interest?.toFixed(0) ?? "—"}`}
              color={DUOLINGO_COLOR}
            />
            <KpiCard
              label="Chess.com App Ratings"
              value={fmt(liveChessCom?.rating_count ?? summary?.appstore.chess_com?.rating_count)}
              sub={`Avg ${(liveChessCom?.avg_rating ?? summary?.appstore.chess_com?.avg_rating ?? 0).toFixed(1)} ★`}
              color={CHESS_COLOR}
            />
            <KpiCard
              label="Duolingo App Ratings"
              value={fmt(liveDuolingo?.rating_count ?? summary?.appstore.duolingo?.rating_count)}
              sub={`Avg ${(liveDuolingo?.avg_rating ?? summary?.appstore.duolingo?.avg_rating ?? 0).toFixed(1)} ★`}
              color={DUOLINGO_COLOR}
            />
          </div>

          {/* ── Trends chart ─────────────────────────────────────────────────── */}
          <div className="panel" style={{ padding: 20, marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 16 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>Web Visit Proxy — Google Trends</div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                  Relative search interest (0–100). Indexed weekly over 5 years.
                </div>
              </div>
              {summary?.as_of && (
                <div style={{ fontSize: 11, color: "var(--muted)" }}>Latest: {summary.as_of}</div>
              )}
            </div>
            {trendChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={trendChartData} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={fmtDate}
                    tick={{ fontSize: 11, fill: "var(--muted)" }}
                    interval="preserveStartEnd"
                    tickCount={8}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 11, fill: "var(--muted)" }}
                    tickFormatter={v => `${v}`}
                  />
                  <Tooltip content={<ChartTooltip unit="idx" />} />
                  <Legend
                    wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                    formatter={v => v === "chess_com" ? "Chess.com" : "Duolingo Chess"}
                  />
                  <Line
                    type="monotone"
                    dataKey="chess_com"
                    name="chess_com"
                    stroke={CHESS_COLOR}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="duolingo_chess"
                    name="duolingo_chess"
                    stroke={DUOLINGO_COLOR}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
                Google Trends data unavailable — refresh to retry.
              </div>
            )}
          </div>

          {/* ── App Store ratings chart ───────────────────────────────────────── */}
          <div className="panel" style={{ padding: 20, marginBottom: 20 }}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Download Proxy — App Store Rating Count</div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                Cumulative iOS App Store ratings. Strong proxy for total downloads. Note: Duolingo tracks the full app (chess is a built-in feature).
              </div>
            </div>
            {ratingChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={ratingChartData} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={fmtDate}
                    tick={{ fontSize: 11, fill: "var(--muted)" }}
                    interval="preserveStartEnd"
                    tickCount={8}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "var(--muted)" }}
                    tickFormatter={v => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : `${(v / 1_000).toFixed(0)}K`}
                    width={50}
                  />
                  <Tooltip content={<ChartTooltip unit="M" />} />
                  <Legend
                    wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                    formatter={v => v === "chess_com" ? "Chess.com" : "Duolingo"}
                  />
                  <Line
                    type="monotone"
                    dataKey="chess_com"
                    name="chess_com"
                    stroke={CHESS_COLOR}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="duolingo"
                    name="duolingo"
                    stroke={DUOLINGO_COLOR}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
                No historical data available.
              </div>
            )}
          </div>

          {/* ── Live App Store snapshot ───────────────────────────────────────── */}
          <div className="panel" style={{ padding: 20, marginBottom: 20 }}>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>
              Live App Store Snapshot (iTunes API)
            </div>
            {appstoreData?.live.length ? (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>App</th>
                      <th>Name</th>
                      <th style={{ textAlign: "right" }}>Rating Count</th>
                      <th style={{ textAlign: "right" }}>Avg Rating</th>
                      <th style={{ textAlign: "right" }}>As Of</th>
                    </tr>
                  </thead>
                  <tbody>
                    {appstoreData.live.map(row => (
                      <tr key={row.app}>
                        <td>
                          <span style={{
                            display: "inline-block", width: 10, height: 10, borderRadius: "50%",
                            background: row.app === "chess_com" ? CHESS_COLOR : DUOLINGO_COLOR,
                            marginRight: 8,
                          }} />
                          {row.app === "chess_com" ? "Chess.com" : "Duolingo"}
                        </td>
                        <td style={{ color: "var(--muted)" }}>{row.app_name}</td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(row.rating_count, 2)}</td>
                        <td style={{ textAlign: "right" }}>{row.avg_rating.toFixed(1)} ★</td>
                        <td style={{ textAlign: "right", color: "var(--muted)" }}>{row.date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                Live App Store data unavailable. Showing curated historical estimates in charts above.
              </div>
            )}
          </div>

          {/* ── Recent trends table ───────────────────────────────────────────── */}
          {recentTrends.length > 0 && (
            <div className="panel" style={{ padding: 20 }}>
              <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>
                Recent Search Interest (last 10 weeks)
              </div>
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th style={{ textAlign: "right", color: CHESS_COLOR }}>Chess.com</th>
                      <th style={{ textAlign: "right", color: DUOLINGO_COLOR }}>Duolingo Chess</th>
                      <th style={{ textAlign: "right" }}>Leader</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentTrends.map(row => {
                      const cc = row.chess_com ?? 0;
                      const dc = row.duolingo_chess ?? 0;
                      const leader = cc > dc ? "Chess.com" : dc > cc ? "Duolingo" : "Tie";
                      const leaderColor = cc > dc ? CHESS_COLOR : dc > cc ? DUOLINGO_COLOR : "var(--muted)";
                      return (
                        <tr key={row.date}>
                          <td>{row.date}</td>
                          <td style={{ textAlign: "right", fontWeight: 600, color: CHESS_COLOR }}>
                            {row.chess_com != null ? row.chess_com.toFixed(1) : "—"}
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 600, color: DUOLINGO_COLOR }}>
                            {row.duolingo_chess != null ? row.duolingo_chess.toFixed(1) : "—"}
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 600, color: leaderColor }}>
                            {leader}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Footer note ───────────────────────────────────────────────────── */}
          <div style={{ marginTop: 20, fontSize: 11, color: "var(--muted)", lineHeight: 1.6 }}>
            <strong>Methodology:</strong> Google Trends interest (0–100) is a relative index of search volume — used as a web visit proxy.
            App Store rating counts are sourced from the iTunes lookup API (live) and curated public estimates (historical) — used as a download proxy.
            Duolingo Chess is a feature within the main Duolingo app; Duolingo overall rating count is shown as the host app proxy.
          </div>
        </>
      )}
    </div>
  );
}
