"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ReferenceLine,
} from "recharts";

interface DataPoint {
  quarter: string;
  actual?: number | null;
  predicted?: number | null;
  lower?: number | null;
  upper?: number | null;
}

interface Props {
  data: DataPoint[];
  metricLabel: string;
  unit?: string;
}

const CustomTooltip = ({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
  unit?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 text-sm shadow-xl">
      <p className="text-slate-300 font-medium mb-2">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm" style={{ background: entry.color }} />
          <span className="text-slate-400">{entry.name}:</span>
          <span className="text-white font-medium">
            {entry.value != null ? `${Number(entry.value).toFixed(1)}${unit ?? ""}` : "—"}
          </span>
        </div>
      ))}
    </div>
  );
};

export default function ActualVsPredicted({ data, metricLabel, unit = "" }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
        No data available
      </div>
    );
  }

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="quarter"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#334155" }}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#334155" }}
            tickFormatter={(v) => `${v}${unit}`}
            width={60}
          />
          <Tooltip content={<CustomTooltip unit={unit} />} />
          <Legend
            wrapperStyle={{ color: "#94a3b8", fontSize: 12, paddingTop: 8 }}
          />

          {/* Confidence band */}
          <Area
            type="monotone"
            dataKey="upper"
            name="Upper CI"
            fill="#f97316"
            fillOpacity={0.1}
            stroke="transparent"
            legendType="none"
          />
          <Area
            type="monotone"
            dataKey="lower"
            name="Lower CI"
            fill="#f97316"
            fillOpacity={0.0}
            stroke="transparent"
            legendType="none"
          />

          {/* Actual bars */}
          <Bar
            dataKey="actual"
            name={`Actual ${metricLabel}`}
            fill="#3b82f6"
            opacity={0.85}
            radius={[2, 2, 0, 0]}
          />

          {/* Predicted line */}
          <Line
            type="monotone"
            dataKey="predicted"
            name={`Predicted ${metricLabel}`}
            stroke="#f97316"
            strokeWidth={2}
            dot={{ fill: "#f97316", r: 3 }}
            connectNulls={false}
            strokeDasharray="4 2"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
