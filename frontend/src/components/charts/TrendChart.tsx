"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface DataPoint {
  date: string;
  [key: string]: number | string;
}

interface SeriesConfig {
  key: string;
  label: string;
  color: string;
}

interface Props {
  data: DataPoint[];
  series: SeriesConfig[];
  title: string;
  height?: number;
}

const COLORS = ["#3b82f6", "#f97316", "#34d399", "#a78bfa", "#fb7185"];

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 text-sm shadow-xl">
      <p className="text-slate-400 text-xs mb-1">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
          <span className="text-slate-300">{entry.name}:</span>
          <span className="text-white font-medium">
            {entry.value != null ? Number(entry.value).toFixed(1) : "—"}
          </span>
        </div>
      ))}
    </div>
  );
};

export default function TrendChart({ data, series, title, height = 200 }: Props) {
  if (!data || data.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center text-slate-500 text-sm gap-1"
        style={{ height }}
      >
        <p className="text-slate-400 text-xs font-medium">{title}</p>
        <p>No signal data available</p>
        <p className="text-xs text-slate-600">Click Refresh to fetch</p>
      </div>
    );
  }

  return (
    <div>
      <p className="text-slate-300 text-sm font-medium mb-2">{title}</p>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              {series.map((s, i) => (
                <linearGradient key={s.key} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={s.color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={s.color} stopOpacity={0.02} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#64748b", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              tickFormatter={(d) => d.slice(0, 7)}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={35}
            />
            <Tooltip content={<CustomTooltip />} />
            {series.length > 1 && (
              <Legend wrapperStyle={{ color: "#64748b", fontSize: 11 }} />
            )}
            {series.map((s, i) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={1.5}
                fill={`url(#grad-${i})`}
                connectNulls={false}
                dot={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
