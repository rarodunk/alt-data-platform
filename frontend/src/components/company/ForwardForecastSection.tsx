"use client";

import { Prediction, ActualMetric } from "@/lib/types";
import {
  ComposedChart, Bar, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";

interface Props {
  metricName: string;
  metricLabel: string;
  unit: string;
  actuals: ActualMetric[];
  forwardPredictions: Prediction[];
}

function fmt(v: number | null | undefined, unit: string) {
  if (v == null) return "—";
  return `${v.toFixed(1)}${unit}`;
}

function horizonLabel(modelVersion: string): string {
  const m = modelVersion.match(/h(\d+)/);
  return m ? `+${m[1]}Q` : "";
}

const CustomTooltip = ({ active, payload, label, unit }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 text-sm shadow-xl">
      <p className="text-slate-300 font-medium mb-2">{label}</p>
      {payload.map((e: any) => (
        <div key={e.name} className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm" style={{ background: e.color }} />
          <span className="text-slate-400">{e.name}:</span>
          <span className="text-white font-medium">
            {e.value != null ? `${Number(e.value).toFixed(1)}${unit ?? ""}` : "—"}
          </span>
        </div>
      ))}
    </div>
  );
};

export default function ForwardForecastSection({
  metricName, metricLabel, unit, actuals, forwardPredictions,
}: Props) {
  const metricActuals = actuals
    .filter(a => a.metric_name === metricName)
    .sort((a, b) => a.period_end.localeCompare(b.period_end));

  const metricPreds = forwardPredictions
    .filter(p => p.metric_name === metricName)
    .sort((a, b) => a.period_end.localeCompare(b.period_end));

  if (metricPreds.length === 0) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h2 className="text-white font-semibold text-lg mb-4">Forward Forecast</h2>
        <p className="text-slate-500 text-sm">No forward predictions yet. Click Refresh to generate.</p>
      </div>
    );
  }

  // Build chart: last 8 actuals + all forward predictions
  const recentActuals = metricActuals.slice(-8);
  const chartData = [
    ...recentActuals.map(a => ({
      quarter: a.quarter,
      actual: a.value,
      predicted: null as number | null,
      lower: null as number | null,
      upper: null as number | null,
      isForecast: false,
    })),
    ...metricPreds.map(p => ({
      quarter: p.quarter,
      actual: null,
      predicted: p.predicted_value,
      lower: p.confidence_lower,
      upper: p.confidence_upper,
      isForecast: true,
    })),
  ];

  // Growth from last actual to each forecast
  const lastActual = metricActuals.at(-1);

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-white font-semibold text-lg">Forward Forecast — {metricLabel}</h2>
          <p className="text-slate-400 text-xs mt-1">
            Training through {metricActuals.at(-1)?.quarter ?? "—"} ·
            Predicting {metricPreds.length} quarter{metricPreds.length !== 1 ? "s" : ""} ahead ·
            CI widens with horizon
          </p>
        </div>
        <div className="flex items-center gap-1.5 bg-amber-900/30 border border-amber-700/40 rounded-lg px-3 py-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
          <span className="text-amber-400 text-xs">Forecast — verify with actuals</span>
        </div>
      </div>

      {/* Forecast cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {metricPreds.map(p => {
          const yoy = lastActual
            ? ((p.predicted_value - lastActual.value) / lastActual.value * 100)
            : null;
          const isUp = yoy != null && yoy > 0;
          const hlabel = p.model_version.match(/h(\d+)/)?.[1];
          return (
            <div key={p.quarter}
              className="bg-slate-900 rounded-xl p-4 border border-slate-700 flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wide">{p.quarter}</p>
                {hlabel && (
                  <span className="text-xs text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">+{hlabel}Q</span>
                )}
              </div>
              <p className="text-xl font-bold text-blue-400">{fmt(p.predicted_value, unit)}</p>
              {p.confidence_lower != null && p.confidence_upper != null && (
                <p className="text-slate-500 text-xs">
                  [{fmt(p.confidence_lower, unit)} – {fmt(p.confidence_upper, unit)}]
                </p>
              )}
              {yoy != null && (
                <div className={`flex items-center gap-1 text-xs font-semibold mt-1 ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                  {isUp ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                  {isUp ? "+" : ""}{yoy.toFixed(1)}% vs last actual
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Chart: actuals + forecast */}
      <div className="w-full h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
            <defs>
              <linearGradient id="fwdCI" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f97316" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#f97316" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="quarter" tick={{ fill: "#94a3b8", fontSize: 11 }}
              tickLine={false} axisLine={{ stroke: "#334155" }} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false}
              axisLine={{ stroke: "#334155" }} tickFormatter={v => `${v}${unit}`} width={62} />
            <Tooltip content={<CustomTooltip unit={unit} />} />
            <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12, paddingTop: 8 }} />

            {/* CI band */}
            <Area type="monotone" dataKey="upper" fill="url(#fwdCI)"
              stroke="transparent" legendType="none" />
            <Area type="monotone" dataKey="lower" fill="#0f172a"
              stroke="transparent" legendType="none" />

            {/* Separator line between actuals and forecast */}
            {recentActuals.length > 0 && (
              <ReferenceLine x={recentActuals.at(-1)?.quarter}
                stroke="#64748b" strokeDasharray="6 3" label={{ value: "▶ Forecast", fill: "#64748b", fontSize: 10 }} />
            )}

            <Bar dataKey="actual" name={`Actual ${metricLabel}`} fill="#3b82f6" opacity={0.85}
              radius={[2, 2, 0, 0]} />
            <Line type="monotone" dataKey="predicted" name={`Forecast ${metricLabel}`}
              stroke="#f97316" strokeWidth={2.5} dot={{ fill: "#f97316", r: 4, strokeWidth: 2 }}
              connectNulls={false} strokeDasharray="6 3" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <p className="text-slate-600 text-xs mt-3 text-center">
        Shaded band = 95% confidence interval · Widens with forecast horizon · Based on ensemble model trained on actuals
      </p>
    </div>
  );
}
