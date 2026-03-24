"use client";

import {
  ComposedChart, Bar, Line, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

export interface MainChartPoint {
  quarter: string;
  actual?: number | null;
  backtest?: number | null;
  forecast?: number | null;
  lower?: number | null;
  upper?: number | null;
}

interface Props {
  data: MainChartPoint[];
  unit?: string;
  height?: number;
}

const CustomTooltip = ({ active, payload, label, unit }: any) => {
  if (!active || !payload?.length) return null;
  const entries = payload.filter((e: any) => e.value != null && e.dataKey !== "lower");
  if (!entries.length) return null;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 shadow-2xl text-sm min-w-[160px]">
      <p className="text-slate-300 font-semibold mb-2">{label}</p>
      {entries.map((e: any) => (
        <div key={e.dataKey} className="flex items-center justify-between gap-4 mb-1">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ background: e.color ?? e.fill }} />
            <span className="text-slate-400 capitalize">{e.name}</span>
          </div>
          <span className="text-white font-medium tabular-nums">
            {Number(e.value).toFixed(1)}{unit}
          </span>
        </div>
      ))}
    </div>
  );
};

export default function MainChart({ data, unit = "", height = 380 }: Props) {
  if (!data.length) return null;

  // Find the last actual quarter for the reference line
  const lastActualQ = [...data].reverse().find(d => d.actual != null)?.quarter;

  // Compute a nice Y domain with some breathing room
  const allVals = data.flatMap(d => [d.actual, d.backtest, d.forecast, d.upper].filter(v => v != null) as number[]);
  const minVal = Math.min(...allVals);
  const maxVal = Math.max(...allVals);
  const pad = (maxVal - minVal) * 0.12;
  const yMin = Math.max(0, Math.floor((minVal - pad) / 10) * 10);
  const yMax = Math.ceil((maxVal + pad) / 10) * 10;

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="ciGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.18} />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.03} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
          <XAxis
            dataKey="quarter"
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={v => `${v}${unit}`}
            width={56}
            domain={[yMin, yMax]}
          />
          <Tooltip content={<CustomTooltip unit={unit} />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />

          {/* CI band */}
          <Area
            type="monotone"
            dataKey="upper"
            fill="url(#ciGrad)"
            stroke="none"
            legendType="none"
            name="upper"
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="lower"
            fill="#020617"
            stroke="none"
            legendType="none"
            name="lower"
            connectNulls
          />

          {/* Actuals bars */}
          <Bar
            dataKey="actual"
            name="Actual"
            fill="#3b82f6"
            radius={[3, 3, 0, 0]}
            maxBarSize={32}
            opacity={0.85}
          />

          {/* Backtest fit line */}
          <Line
            type="monotone"
            dataKey="backtest"
            name="Model fit"
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={false}
            strokeDasharray="4 3"
            connectNulls
          />

          {/* Forward forecast line */}
          <Line
            type="monotone"
            dataKey="forecast"
            name="Forecast"
            stroke="#f59e0b"
            strokeWidth={2.5}
            dot={{ fill: "#f59e0b", r: 4, strokeWidth: 0 }}
            connectNulls
          />

          {/* Divider between actuals and forecast */}
          {lastActualQ && (
            <ReferenceLine
              x={lastActualQ}
              stroke="#334155"
              strokeWidth={1.5}
              strokeDasharray="6 4"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
