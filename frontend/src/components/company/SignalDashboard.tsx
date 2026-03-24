"use client";

import { SignalPoint } from "@/lib/types";
import TrendChart from "@/components/charts/TrendChart";

interface Props {
  signals: SignalPoint[];
  company: string;
}

const COLORS = ["#3b82f6", "#f97316", "#34d399", "#a78bfa", "#fb7185", "#fbbf24"];

export default function SignalDashboard({ signals, company }: Props) {
  // Group signals by source
  const bySource: Record<string, SignalPoint[]> = {};
  for (const s of signals) {
    if (!bySource[s.source]) bySource[s.source] = [];
    bySource[s.source].push(s);
  }

  const sourceEntries = Object.entries(bySource);

  if (sourceEntries.length === 0) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h2 className="text-white font-semibold text-lg mb-4">Alternative Data Signals</h2>
        <div className="text-slate-500 text-sm text-center py-8">
          <p>No signal data yet.</p>
          <p className="text-xs mt-1 text-slate-600">Click "Refresh Data" to fetch Google Trends, Reddit, and flight data.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
      <h2 className="text-white font-semibold text-lg mb-6">Alternative Data Signals</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {sourceEntries.map(([source, points]) => {
          // Get unique metric names (keywords / fields)
          const metricNames = Array.from(new Set(points.map((p) => p.metric_name)));

          // Build chart data: date -> {metric: value}
          const byDate: Record<string, Record<string, number>> = {};
          for (const p of points) {
            if (!byDate[p.date]) byDate[p.date] = {};
            byDate[p.date][p.metric_name] = p.value;
          }
          const chartData = Object.entries(byDate)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([date, values]) => ({ date, ...values }));

          const series = metricNames.slice(0, 5).map((name, i) => ({
            key: name,
            label: name.replace(/_/g, " "),
            color: COLORS[i % COLORS.length],
          }));

          const sourceLabel =
            source === "google_trends"
              ? "Google Trends"
              : source === "reddit"
              ? "Reddit Activity"
              : source === "opensky"
              ? "Flight Tracker (OpenSky)"
              : source.replace(/_/g, " ");

          return (
            <div key={source} className="bg-slate-900 rounded-lg p-4">
              <TrendChart
                data={chartData}
                series={series}
                title={sourceLabel}
                height={180}
              />
              {source.includes("placeholder") && (
                <p className="text-yellow-500 text-xs mt-2">
                  Showing placeholder data — configure API credentials for live data.
                </p>
              )}
            </div>
          );
        })}

        {/* TransMedics flight callout */}
        {company === "transmedics" && (
          <div className="bg-slate-900 border border-slate-600 rounded-lg p-4 md:col-span-2">
            <p className="text-slate-300 text-sm font-medium mb-2">Flight Tracking Setup</p>
            <p className="text-slate-500 text-xs leading-relaxed">
              TransMedics operates a proprietary aviation logistics network. To enable flight
              tracking via OpenSky Network:
            </p>
            <ol className="text-slate-500 text-xs mt-2 list-decimal list-inside space-y-1">
              <li>
                Search for "TransMedics" at{" "}
                <span className="text-blue-400">registry.faa.gov/AircraftInquiry/</span>
              </li>
              <li>Note the N-numbers (tail numbers) of owned aircraft</li>
              <li>Convert to ICAO24 hex codes using FAA registry tools</li>
              <li>
                Add to <code className="text-slate-400 bg-slate-800 px-1 rounded">.env</code> as{" "}
                <code className="text-slate-400 bg-slate-800 px-1 rounded">TMDX_AIRCRAFT_ICAO24=hex1,hex2,...</code>
              </li>
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}
